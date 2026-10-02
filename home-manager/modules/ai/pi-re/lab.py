#!/usr/bin/env python3
"""Start/stop the owned rooted Android + scoped MITM + Frida lab as one unit."""

import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from android import Android, LabError, read_json, safe_path, write_json
from runtime import Frida, bounded_run, device_arguments, local_environment
from system_ca import SystemCA
from traffic import Traffic


class Lab:
    def __init__(self, config, state_dir):
        self.config = config
        self.android = Android(config, state_dir)
        self.traffic = Traffic(config, self.android)
        self.proxy_record = safe_path(self.android.state / "android-proxy.json")

    def shell(self, args):
        code, text = self.android.adb(["shell", shlex.join(args)])
        if code:
            raise LabError("Selected lab Android proxy operation failed")
        return text.strip()

    def retire_device(self, close_session=True):
        # Only the private device daemon selected by the same reviewed routing.
        # Ordinary close retires its helper/forward; daemon stop clears per-serial
        # caches after abnormal guest loss. Never close --shutdown/global kill.
        state = safe_path(self.android.state / "device")
        if not state.exists():
            return {"status": "ok", "state": "absent"}
        owner = self.android.owner()
        route = device_arguments(self.config, self.android, ["close", "--json"], owner)
        errors = []
        cancelled = False
        if close_session:
            try:
                bounded_run(
                    route,
                    local_environment(self.android),
                    self.android.state / "device-cleanup",
                    15,
                )
            except (LabError, OSError, KeyboardInterrupt) as error:
                cancelled |= isinstance(error, KeyboardInterrupt)
                errors.append(str(error) or "Owned device close interrupted")
        # This official command verifies daemon PID/start identity. It affects
        # only this profile's state-dir, even if a close request failed.
        try:
            result = bounded_run(
                [
                    self.config["agentDevice"],
                    "--state-dir",
                    str(state),
                    "--config",
                    str(Path(__file__).parent / "agent-device.json"),
                    "daemon",
                    "stop",
                    "--json",
                ],
                local_environment(self.android),
                self.android.state / "device-cleanup",
                15,
            )
        except (LabError, OSError, KeyboardInterrupt) as error:
            cancelled |= isinstance(error, KeyboardInterrupt)
            errors.append(str(error) or "Owned device daemon stop interrupted")
            result = None
        if cancelled:
            raise KeyboardInterrupt("; ".join(errors))
        if errors:
            raise LabError("Owned device cleanup incomplete: " + "; ".join(errors))
        return result

    def framework_ready(self):
        # sys.boot_completed can remain1 during a system_server restart. Do not
        # treat an unavailable PackageManager/provider as an absent fixture APK.
        deadline = time.monotonic() + 60
        stable = 0
        while time.monotonic() < deadline:
            try:
                code, package = self.android.adb(
                    ["shell", "pm", "path", "android"],
                    min(5, max(0.1, deadline - time.monotonic())),
                )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                settings_code, proxy = self.android.adb(
                    ["shell", "settings", "get", "global", "http_proxy"], min(5, remaining)
                )
                valid = (
                    code == 0
                    and package.strip().startswith("package:/")
                    and settings_code == 0
                    and "Exception" not in proxy
                    and "Error" not in proxy
                )
                stable = stable + 1 if valid else 0
                if stable >= 3:
                    return
            except LabError:
                stable = 0
            time.sleep(min(1, max(0, deadline - time.monotonic())))
        raise LabError(
            "Android framework providers/package manager did not stabilize within60s", True
        )

    def configure_proxy(self, port):
        assigned = f"10.0.2.2:{port}"
        owner = self.android.owner()["token"]
        previous = self.shell(["settings", "get", "global", "http_proxy"])
        if previous in ("", ":0"):
            previous = "null"
        if self.proxy_record.exists():
            record = read_json(self.proxy_record)
            if record.get("owner") == owner:
                if previous == record.get("assigned"):
                    previous = "null" if record["previous"] in ("", ":0") else record["previous"]
                elif previous != (
                    "null" if record.get("previous") in ("", ":0") else record.get("previous")
                ):
                    raise LabError("Lab proxy changed outside this run; refusing to overwrite it")
        # Publish the recovery record before changing Android's persistent setting.
        write_json(
            self.proxy_record,
            {"version": 1, "owner": owner, "previous": previous, "assigned": assigned},
        )
        self.shell(["settings", "put", "global", "http_proxy", assigned])
        if self.shell(["settings", "get", "global", "http_proxy"]) != assigned:
            raise LabError("Android proxy setting did not take effect")
        return assigned

    def restore_proxy(self):
        if not self.proxy_record.exists():
            return
        record = read_json(self.proxy_record)
        if record.get("owner") != self.android.owner()["token"]:
            raise LabError("Proxy metadata belongs to a different AVD generation")
        current = self.shell(["settings", "get", "global", "http_proxy"])
        if current in ("", ":0"):
            current = "null"
        previous = "null" if record["previous"] in ("", ":0") else record["previous"]
        if current != record.get("assigned"):
            if current == previous:
                write_json(self.proxy_record, {**record, "phase": "restored"})
                return
            raise LabError("Lab proxy was changed externally; preserving that setting")
        if previous in ("null", "", ":0"):
            self.shell(["settings", "delete", "global", "http_proxy"])
        else:
            self.shell(["settings", "put", "global", "http_proxy", previous])
        # SettingsProvider writes asynchronously. Retain recovery ownership even
        # after restoration, so abrupt VM death cannot turn our stale assignment
        # into a falsely adopted baseline on the next boot.
        write_json(self.proxy_record, {**record, "phase": "restored"})
        time.sleep(2.1)

    def start(self, hosts=None, visible=False):
        android = self.android
        with android.lock():
            android.create()
            existed = bool(android.lease()[1])
            traffic_started = False
            proxy_configured = False
            stage = "cold device daemon cleanup"
            try:
                if not existed:
                    self.retire_device(close_session=False)
                stage = "boot/root"
                device = android.start(visible)
                stage = "framework readiness"
                self.framework_ready()
                stage = "capture start"
                traffic = self.traffic.start(hosts)
                traffic_started = not traffic.get("reused", False)
                stage = "system CA"
                certificate = SystemCA(android, self.config["traffic"]["openssl"]).install(
                    traffic["caCertificate"]
                )
                stage = "proxy configuration"
                proxy_configured = True
                proxy = self.configure_proxy(traffic["proxyPort"])
                stage = "Frida setup"
                frida = Frida(self.config, android).setup()
                stage = "post-provision framework readiness"
                self.framework_ready()
                return {
                    "status": "ok",
                    "android": device,
                    "traffic": traffic,
                    "systemCA": certificate,
                    "proxy": proxy,
                    "frida": frida,
                    "scope": "all-proxy-hostnames" if hosts is None else hosts,
                    "trust": "owned-guest-only; TLS pinning is separate",
                }
            except (Exception, KeyboardInterrupt) as error:
                cleanup_errors = []
                actions = []
                if proxy_configured:
                    actions.append(self.restore_proxy)
                if traffic_started:
                    actions.append(self.traffic.stop)
                if not existed:
                    actions.append(lambda: android.stop(graceful=False))
                for action in actions:
                    try:
                        action()
                    except (LabError, OSError) as cleanup_error:
                        cleanup_errors.append(str(cleanup_error))
                if cleanup_errors:
                    raise LabError(
                        "Lab startup failed; recovery needed: " + "; ".join(cleanup_errors)
                    ) from error
                if isinstance(error, LabError):
                    raise LabError(f"Lab {stage}: {error}", error.timeout) from error
                raise

    def status(self):
        # No ADB, root, listener probes, initialization, or process signals.
        return {
            "status": "ok",
            "android": self.android.execute("status"),
            "traffic": self.traffic.status(),
            "inspection": "metadata/process-only",
            "systemCA": "uninspected",
            "proxyRecordPresent": self.proxy_record.exists(),
        }

    def stop(self):
        android = self.android
        errors = []
        cancelled = False

        def attempt(action):
            nonlocal cancelled
            try:
                return action()
            except (Exception, KeyboardInterrupt) as error:
                cancelled |= isinstance(error, KeyboardInterrupt)
                errors.append(str(error) or "Cleanup interrupted")
                return None

        # A start must not interleave between VM shutdown and capture shutdown.
        with android.lock():
            device = {"status": "unknown", "state": "uninspected"}
            capture = {"status": "unknown", "state": "uninspected"}
            try:
                if android.owner(required=False):
                    if android.lease()[1]:
                        rooted = attempt(
                            lambda: android.root_device(
                                android.backend.now() + min(android.timeout, 30)
                            )
                        )
                        if rooted is not None:
                            attempt(self.retire_device)
                            attempt(self.restore_proxy)
                            attempt(lambda: Frida(self.config, android).stop())
                            # QEMU termination is not a guest filesystem shutdown.
                            # Persist APK/SettingsProvider writes before powering off.
                            attempt(lambda: self.shell(["sync"]))
                        # Guest stop removes all boot-scoped certificate overlays.
                        attempt(lambda: android.stop(graceful=False))
                    device = attempt(android.status) or device
                else:
                    device = android.result("absent")
            except (Exception, KeyboardInterrupt) as error:
                cancelled |= isinstance(error, KeyboardInterrupt)
                errors.append(str(error) or "Guest cleanup interrupted")
            finally:
                # Also retire host-side state if root/guest cleanup was unavailable.
                attempt(lambda: self.retire_device(close_session=False))
                # Independently owned traffic is cleaned even after guest failure.
                capture = attempt(self.traffic.stop) or capture
        result = {
            "status": "cancelled" if cancelled else "partial" if errors else "ok",
            "android": device,
            "traffic": capture,
            "systemCA": "inactive-after-guest-stop"
            if device.get("state") in ("stopped", "absent")
            else "uninspected",
        }
        if errors:
            result["recoveryWarnings"] = errors
        return result


def run_check(config, config_path, state_dir):
    """Separate 600-second qualification budget and an owned process group."""
    from subagent import child_running, die_with_helper

    root = safe_path(state_dir / "qualification")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    job = root / ("check-" + uuid.uuid4().hex)
    job.mkdir(mode=0o700)
    parent = os.getpid()
    interrupted = None
    with (job / "stdout.json").open("xb") as out, (job / "stderr.txt").open("xb") as err:
        os.chmod(out.name, 0o600)
        os.chmod(err.name, 0o600)
        proc = subprocess.Popen(
            [
                config["python"],
                str(Path(config["resources"]) / "verify_lab.py"),
                "--config",
                str(config_path),
                "--state-dir",
                str(state_dir),
            ],
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            start_new_session=True,
            preexec_fn=lambda: die_with_helper(parent),
        )
        deadline = time.monotonic() + 600
        try:
            while child_running(proc):
                if time.monotonic() >= deadline:
                    raise LabError("Lab qualification exceeded its 600-second budget", True)
                time.sleep(0.05)
        except (Exception, KeyboardInterrupt) as error:
            interrupted = error
        finally:
            # Leader remains unreaped until both signals: no stale group-ID kill.
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(proc.pid, sig)
                except ProcessLookupError:
                    pass
                if sig == signal.SIGTERM:
                    end = time.monotonic() + 0.75
                    while child_running(proc) and time.monotonic() < end:
                        time.sleep(0.025)
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired as error:
                interrupted = error
    if interrupted is not None:
        recovery = Lab(config, state_dir).stop()
        raise LabError(
            f"Lab qualification interrupted; cleanup status: {recovery['status']}; diagnostics: {job}",
            isinstance(interrupted, (LabError, subprocess.TimeoutExpired)),
        ) from interrupted
    output = job / "stdout.json"
    if output.stat().st_size > 16384:
        raise LabError(f"Qualification result exceeded 16 KiB; diagnostics: {job}")
    result = json.loads(output.read_text())
    if not isinstance(result, dict) or "status" not in result:
        raise LabError(f"Invalid qualification result; diagnostics: {job}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("command", choices=("start", "status", "stop", "check"))
    parser.add_argument("--allow-host", action="append", default=[])
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command != "start" and (args.visible or args.allow_host):
        parser.error("--visible/--allow-host apply only to start")
    try:
        config = json.loads(args.config.read_text())
        if args.command == "check":
            result = run_check(config, args.config, args.state_dir)
        else:
            lab = Lab(config, args.state_dir)
            result = (
                lab.start(args.allow_host or None, args.visible)
                if args.command == "start"
                else getattr(lab, args.command)()
            )
        print(json.dumps(result, indent=2 if args.json else None))
        return 0 if result["status"] == "ok" else 1
    except (LabError, OSError, ValueError, KeyError) as error:
        print(
            json.dumps(
                {
                    "status": "timeout"
                    if isinstance(error, LabError) and error.timeout
                    else "blocked",
                    "error": str(error),
                }
            )
        )
        return 1
    except KeyboardInterrupt:
        print(json.dumps({"status": "cancelled", "error": "Lab operation cancelled"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
