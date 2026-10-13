#!/usr/bin/env python3
"""Read one documentation page with a fresh, owned Chrome DevTools CLI instance."""

import argparse
import contextlib
import json
import os
import select
import selectors
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from initialize import write_private
from research import process_identity
from subagent import child_running, private_directory


class BrowserError(ValueError):
    pass


def validate_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or len(url) > 8192
        or "\0" in url
    ):
        raise BrowserError("Use one approved HTTP(S) documentation URL without credentials")


def cli_call(cli, session, arguments, environment, *, timeout=30, cancelled=None):
    # Capture only bounded CLI output; a timeout stops this invocation, never a global daemon.
    if cancelled is not None and cancelled():
        raise BrowserError("Documentation browser read cancelled")
    proc = subprocess.Popen(
        [cli, "--sessionId", session, *arguments],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    stdout = bytearray()
    total = 0
    started = time.monotonic()
    try:
        with selectors.DefaultSelector() as selector:
            for stream in (proc.stdout, proc.stderr):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)
            while selector.get_map() or child_running(proc):
                if cancelled is not None and cancelled():
                    raise BrowserError("Documentation browser read cancelled")
                if time.monotonic() - started > timeout:
                    raise BrowserError("Documentation browser command exceeded its time budget")
                for ready, _ in selector.select(timeout=0.05):
                    chunk = os.read(ready.fd, 65536)
                    if not chunk:
                        selector.unregister(ready.fileobj)
                        continue
                    total += len(chunk)
                    if total > 1024 * 1024:
                        raise BrowserError("Documentation browser command exceeded its byte budget")
                    if ready.fileobj is proc.stdout:
                        stdout.extend(chunk)
    finally:
        # Leader is unreaped, preventing process-group identity reuse during cleanup.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGTERM)
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        proc.stdout.close()
        proc.stderr.close()
    if proc.returncode:
        raise BrowserError(
            "Pinned Chrome DevTools CLI command failed; raw browser diagnostics were not forwarded"
        )
    return bytes(stdout)


def acquire_daemon(pid_file, settings, run_id, environment):
    pid = int(pid_file.read_text().strip())
    daemon = process_identity(pid)
    if not daemon:
        raise BrowserError("Dedicated browser daemon exited before ownership was established")
    cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    if not any(
        argument
        and Path(os.fsdecode(argument)).resolve() == Path(settings["daemonScript"]).resolve()
        for argument in cmdline
    ):
        raise BrowserError("Dedicated browser daemon identity does not match the pinned runtime")
    inherited = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    expected = {
        "CHROME_DEVTOOLS_MCP_SESSION_ID": run_id,
        "HOME": environment["HOME"],
        "XDG_RUNTIME_DIR": environment["XDG_RUNTIME_DIR"],
    }
    if any(f"{key}={value}".encode() not in inherited for key, value in expected.items()):
        raise BrowserError("Dedicated browser daemon does not own this namespace/profile")
    pidfd = os.pidfd_open(pid)
    if process_identity(pid) != daemon:
        os.close(pidfd)
        raise BrowserError("Dedicated browser daemon changed while acquiring ownership")
    return daemon, pidfd


def read_page(config, state, url, *, cancelled=None):
    validate_url(url)
    if os.environ.get("PI_RE_CHILD") == "1" or os.environ.get("PI_RE_RESEARCH") == "1":
        raise BrowserError("Browser lifecycle is root-only, not a research-worker tool")
    settings = config["browser"]
    for key in ("cli", "executable", "daemonScript"):
        if not Path(settings[key]).is_absolute() or not Path(settings[key]).is_file():
            raise BrowserError("Pinned documentation browser resource is unavailable")
    run_id = uuid.uuid4().hex
    artifact = state / "browser" / run_id
    private_directory(state)
    private_directory(state / "browser")
    private_directory(artifact)
    # Keep the Unix socket path short and private, regardless of caller HOME/XDG length.
    scratch = Path(tempfile.mkdtemp(prefix="prb-", dir="/tmp"))
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(scratch / "home"),
        "LANG": "C.UTF-8",
        "TMPDIR": str(scratch / "tmp"),
        "XDG_RUNTIME_DIR": str(scratch / "runtime"),
        "XDG_CONFIG_HOME": str(scratch / "config"),
        "XDG_CACHE_HOME": str(scratch / "cache"),
        "XDG_DATA_HOME": str(scratch / "data"),
        "XDG_STATE_HOME": str(scratch / "state"),
        "CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS": "1",
        "CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS": "1",
    }
    for value in environment.values():
        if value.startswith(str(scratch)):
            private_directory(Path(value))
    pid_file = scratch / "runtime" / ("chrome-devtools-mcp-" + run_id) / "daemon.pid"
    daemon = None
    pidfd = None
    page_id = None
    cleanup = False
    result = None
    failure = None
    recording_error = False
    try:
        cli_call(
            settings["cli"],
            run_id,
            [
                "start",
                "--headless=true",
                "--executablePath=" + settings["executable"],
                "--userDataDir=" + str(scratch / "profile"),
                "--workspace=" + str(scratch),
                "--usageStatistics=false",
                "--performanceCrux=false",
                "--sourceMaps=false",
                "--javascriptEvaluation=false",
                "--categoryInput=false",
                "--categoryNetwork=false",
                "--categoryEmulation=false",
                "--categoryPerformance=false",
                "--categoryExtensions=false",
                "--categoryMemory=false",
            ],
            environment,
            cancelled=cancelled,
        )
        daemon, pidfd = acquire_daemon(pid_file, settings, run_id, environment)
        write_private(
            artifact / "owner.json",
            {
                "session": run_id,
                "daemon": daemon,
                "scratch": str(scratch),
                "profile": str(scratch / "profile"),
                "url": url,
            },
        )
        opened = json.loads(
            cli_call(
                settings["cli"],
                run_id,
                [
                    "new_page",
                    url,
                    "--isolatedContext=" + run_id,
                    "--timeout=15000",
                    "--output-format=json",
                ],
                environment,
                cancelled=cancelled,
            )
        )
        selected = [page for page in opened.get("pages", []) if page.get("selected")]
        if len(selected) != 1 or type(selected[0].get("id")) is not int:
            raise BrowserError("Dedicated browser did not return one owned page ID")
        page_id = selected[0]["id"]
        snapshot = scratch / "snapshot.txt"
        cli_call(
            settings["cli"],
            run_id,
            ["take_snapshot", str(page_id), "--filePath=" + str(snapshot), "--output-format=json"],
            environment,
            cancelled=cancelled,
        )
        with snapshot.open("rb") as stream:
            raw = stream.read(64 * 1024 + 1)
        text = raw[: 64 * 1024].decode("utf-8", errors="replace")
        write_private(
            artifact / "snapshot.json",
            {"pageId": page_id, "url": selected[0].get("url"), "text": text},
        )
        result = {
            "status": "ok",
            "session": run_id,
            "pageId": page_id,
            "url": selected[0].get("url"),
            "snapshot": text,
            "truncated": len(raw) > 64 * 1024,
            "artifact": str(artifact),
            "executionMode": "dedicated-browser-not-host-sandbox",
        }
    except (ValueError, OSError) as error:
        failure = error
    finally:
        # Startup can fail/cancel after forking the daemon. Recover only our fresh
        # namespace with the same pinned-script and process-identity checks.
        if pidfd is None:
            reconciliation_end = time.monotonic() + 5
            while pidfd is None and time.monotonic() < reconciliation_end:
                # Publication includes create/truncate then write: existence alone
                # is not readiness. Retry boundedly, never signal without proof.
                with contextlib.suppress(ValueError, OSError):
                    daemon, pidfd = acquire_daemon(pid_file, settings, run_id, environment)
                if pidfd is None:
                    time.sleep(0.05)
            if pidfd is not None:
                try:
                    write_private(
                        artifact / "owner.json",
                        {
                            "session": run_id,
                            "daemon": daemon,
                            "scratch": str(scratch),
                            "profile": str(scratch / "profile"),
                            "url": url,
                        },
                    )
                except OSError:
                    recording_error = True  # Disk/quota failure must not skip owned cleanup.
        if page_id is not None and pidfd is not None and process_identity(daemon["pid"]) == daemon:
            with contextlib.suppress(ValueError, OSError):
                cli_call(
                    settings["cli"],
                    run_id,
                    ["close_page", str(page_id), "--output-format=json"],
                    environment,
                    timeout=5,
                )
        if pidfd is not None:
            # A pidfd targets the proven owned daemon even if the numeric PID is later reused.
            try:
                with contextlib.suppress(ProcessLookupError):
                    signal.pidfd_send_signal(pidfd, signal.SIGTERM)
                cleanup = bool(select.select([pidfd], [], [], 8)[0])
            finally:
                os.close(pidfd)
        if cleanup:
            import shutil

            shutil.rmtree(scratch)
        try:
            write_private(artifact / "cleanup.json", {"complete": cleanup, "scratch": str(scratch)})
        except OSError:
            recording_error = True
    record_note = " (artifact recording failed)" if recording_error else ""
    if failure is None and cancelled is not None and cancelled():
        failure = BrowserError("Documentation browser read cancelled")
    if not cleanup:
        raise BrowserError(
            f"Browser cleanup/ownership is unresolved; private recovery record: {artifact}{record_note}"
        ) from failure
    if failure is not None:
        raise BrowserError(
            f"Documentation browser read failed; private record: {artifact}{record_note}"
        ) from failure
    result["cleanupComplete"] = cleanup
    if recording_error:
        result["artifactRecordingError"] = "Cleanup completed but artifact recording failed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("operation", choices=("read",))
    parser.add_argument("url")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cancel_requested = False

    def cancel(_signum, _frame):
        nonlocal cancel_requested
        # Active commands check this flag. Resource retirement never raises
        # asynchronously, even for a first signal arriving during recovery.
        cancel_requested = True

    old_signals = {sig: signal.signal(sig, cancel) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        result = read_page(
            json.loads(args.config.read_text()),
            args.state_dir,
            args.url,
            cancelled=lambda: cancel_requested,
        )
        if args.json:
            print(json.dumps(result))
        else:
            print(f"Source: {result['url']}\n\n{result['snapshot']}")
            if result["truncated"]:
                print("\n[Documentation snapshot truncated to 64 KiB]")
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f"pi-re browser: {error}\n")
    finally:
        for sig, handler in old_signals.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    main()
