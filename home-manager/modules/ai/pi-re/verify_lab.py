#!/usr/bin/env python3
"""Owned-fixture live qualification, not a claim of general agent readiness."""

import argparse
import copy
import http.server
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from android import LabError, read_json, safe_path, write_json
from lab import Lab
from runtime import device

PACKAGE = "org.pi.re.fixture"
HOST = "pi-re.fixture.test"


def command(argv, timeout=60, env=None):
    result = subprocess.run(
        [str(x) for x in argv],
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
        check=False,
    )
    if result.returncode:
        raise LabError("Owned fixture build/certificate command failed")
    if len(result.stdout.encode()) > 16384:
        raise LabError("Fixture command exceeded output budget")
    return result.stdout


def signer(tool, apk):
    output = command([tool, "verify", "--print-certs", apk])
    matches = re.findall(r"Signer #1 certificate SHA-256 digest: ([0-9a-f]{64})", output)
    if len(matches) != 1:
        raise LabError("Cannot verify owned fixture signer")
    return matches[0]


def nodes(config, android):
    result = device(config, android, ["snapshot", "--json"])
    if result["status"] != "ok" or not result["result"].get("success"):
        raise LabError("Owned fixture semantic snapshot failed")
    data = result["result"]["data"]
    if data.get("appBundleId") != PACKAGE or data.get("truncated"):
        raise LabError("Snapshot is not the complete owned fixture")
    return data["nodes"]


def click(config, android, description):
    candidates = [n for n in nodes(config, android) if n.get("contentDescription") == description]
    if len(candidates) != 1:
        raise LabError("Owned fixture button is not uniquely addressable")
    ref = candidates[0]["ref"]
    result = device(config, android, ["click", "@" + ref.removeprefix("@"), "--json"])
    if result["status"] != "ok" or not result["result"].get("success"):
        raise LabError("Owned fixture fresh-ref click failed")


def cleanup(lab, session, server, failed):
    errors = []
    actions = []
    if session is not None:
        actions.append(session.detach)
    if server:
        actions.extend((server.shutdown, server.server_close))
    if lab:
        actions.append(lab.stop if failed else lab.traffic.stop)
    for action in actions:
        try:
            result = action()
            if isinstance(result, dict) and result.get("status") != "ok":
                errors.append("Owned resource cleanup remains incomplete")
        except (Exception, KeyboardInterrupt) as error:
            errors.append(str(error) or "Cleanup interrupted")
    if errors:
        raise LabError("Qualification cleanup needs recovery: " + "; ".join(errors))


def verify(config, state_dir):
    # The check intentionally replaces only this profile's owned fixture capture.
    # Other active scope/configuration is refused by Traffic's lease matching.
    import frida
    from mitmproxy import io

    original = Lab(config, state_dir)
    root = safe_path(state_dir / "qualification")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex
    proof = "ok:" + nonce
    job = root / ("lab-" + nonce)
    job.mkdir(mode=0o700)
    report = {
        "status": "ok",
        "qualification": "owned-fixture/manual-tool-paths",
        "workflowQualification": "pending clean-session agent trials",
        "checks": {},
    }
    server = None
    session = None
    lab = None
    failed = True
    phase = "capture scope validation"
    try:
        status = original.traffic.status()
        if status["state"] != "absent":
            original.traffic.start(None if status.get("captureMode") == "all" else [HOST])
            # Validate current all-host or fixture-only scope before replacement.
        # Adopt cleanup ownership only AFTER validation; a different active scope
        # must not be disrupted. All later side effects are inside this boundary.
        lab = original
        if status["state"] != "absent":
            original.traffic.stop()
        with tempfile.TemporaryDirectory(prefix="tls-", dir=job) as temporary:
            temporary = Path(temporary)
            private_key = temporary / "origin-key.pem"
            public_cert = temporary / "origin-cert.pem"
            phase = "origin certificate"
            command(
                [
                    config["traffic"]["openssl"],
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-keyout",
                    private_key,
                    "-out",
                    public_cert,
                    "-days",
                    "1",
                    "-subj",
                    f"/CN={HOST}",
                    "-addext",
                    f"subjectAltName=DNS:{HOST}",
                ]
            )
            private_key.chmod(0o600)

            class Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path != "/proof?nonce=" + nonce:
                        self.send_error(404)
                        return
                    body = proof.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, *_args):
                    pass

            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            server.daemon_threads = True
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(public_cert, private_key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            selected = copy.deepcopy(config)
            selected["traffic"]["fixture"] = {
                "host": HOST,
                "port": server.server_port,
                "caCertificate": str(public_cert),
            }
            lab = Lab(selected, state_dir)
            phase = "lab startup"
            startup = lab.start([HOST])
            android = lab.android
            report["checks"]["rootUID"] = lab.shell(["id", "-u"])
            report["checks"]["systemCA"] = startup["systemCA"]
            report["checks"]["SELinux"] = lab.shell(["getenforce"])
            if report["checks"]["rootUID"] != "0" or report["checks"]["SELinux"] != "Enforcing":
                raise LabError("Fixture requires verified root and unchanged enforcing SELinux")
            tools = Path(config["android"]["sdkRoot"]) / "build-tools/35.0.0"
            known = safe_path(state_dir / "fixtures/android-fixture.apk")
            phase = "fixture provenance/package manager"
            code, installed = android.adb(["shell", "pm", "path", PACKAGE])
            if code == 0 and installed.strip():
                location = installed.strip().removeprefix("package:")
                if (
                    not re.fullmatch(r"/data/app/[A-Za-z0-9/_=+.~\-]+/base\.apk", location)
                    or not known.is_file()
                ):
                    raise LabError("Existing fixture package has no verified owned APK provenance")
                pulled = job / "previous.apk"
                code, _ = android.adb(["pull", location, str(pulled)], 30)
                if code or signer(tools / "apksigner", pulled) != signer(
                    tools / "apksigner", known
                ):
                    raise LabError("Existing fixture signer does not match the owned APK")
                code, _ = android.adb(["uninstall", PACKAGE], 30)
                if code:
                    raise LabError("Owned fixture replacement failed")
            fixture = Path(config["resources"]) / "fixture"
            environment = dict(os.environ, JAVA_HOME=config["jdk"])
            environment["PATH"] = (
                str(Path(config["jdk"]) / "bin") + os.pathsep + environment.get("PATH", "")
            )
            apk = job / "fixture.apk"
            phase = "owned fixture build"
            command(
                [
                    config["python"],
                    fixture / "build.py",
                    "--sdk-root",
                    config["android"]["sdkRoot"],
                    "--jdk",
                    config["jdk"],
                    "--output",
                    apk,
                ],
                240,
                environment,
            )
            known.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            # Save the exact approved APK BEFORE installing, for recoverable provenance.
            known.write_bytes(apk.read_bytes())
            known.chmod(0o600)
            phase = "owned fixture install"
            code, install_output = android.adb(["install", str(apk)], 90)
            write_json(job / "install.json", {"exitCode": code, "output": install_output[:16384]})
            if code:
                raise LabError(
                    f"Owned HTTPS fixture installation failed; diagnostics: {job / 'install.json'}"
                )
            phase = "semantic UI/Java hook"
            device(selected, android, ["open", PACKAGE, "--no-test-ime", "--json"])
            lab.shell(["am", "force-stop", PACKAGE])
            lab.shell(
                [
                    "am",
                    "start",
                    "-n",
                    PACKAGE + "/.MainActivity",
                    "--es",
                    "fixture_url",
                    f"https://{HOST}/proof?nonce={nonce}",
                ]
            )
            time.sleep(0.5)
            captured = []
            ready = threading.Event()
            incremented = threading.Event()

            def on_message(message, _data):
                if len(captured) < 25:
                    captured.append(message)
                payload = message.get("payload", {})
                if isinstance(payload, dict) and payload.get("event") == "hook-ready":
                    ready.set()
                if (
                    isinstance(payload, dict)
                    and payload.get("event") == "increment"
                    and payload.get("result") == 1
                ):
                    incremented.set()

            target = frida.get_device(android.serial, timeout=5)
            matches = [
                app
                for app in target.enumerate_applications()
                if app.identifier == PACKAGE and app.pid
            ]
            if len(matches) != 1:
                raise LabError("Cannot select the owned fixture process by package ID")
            session = target.attach(matches[0].pid)
            source = (
                Path(config["frida"]["javaBridge"]).read_text()
                + """
            globalThis.Java = bridge;
            Java.perform(() => {
              const Activity = Java.use('org.pi.re.fixture.MainActivity');
              const increment = Activity.increment.overload();
              increment.implementation = function () {
                const result = increment.call(this);
                send({event:'increment', result});
                return result;
              };
              send({event:'hook-ready'});
            });
            """
            )
            script = session.create_script(source)
            script.on("message", on_message)
            script.load()
            if not ready.wait(15):
                raise LabError("Pinned Java bridge hook did not become ready")
            click(selected, android, "Increment fixture counter")
            if not incremented.wait(5) or not any(
                n.get("label") == "Counter: 1" for n in nodes(selected, android)
            ):
                raise LabError("Actual UI click did not correlate with Java increment event")
            report["checks"]["uiJavaCorrelation"] = {
                "event": "increment",
                "result": 1,
                "UI": "Counter: 1",
                "bridge": "bundled-frida-tools",
            }
            write_json(job / "java-events.json", captured)
            session.detach()
            session = None
            phase = "default HTTPS/traffic"
            click(selected, android, "Fetch HTTPS fixture")
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if any(n.get("label") == "HTTPS: " + proof for n in nodes(selected, android)):
                    break
                time.sleep(0.25)
            else:
                raise LabError("Default Android HTTPS trust/proxy/capture correlation failed")
            import socket

            with socket.create_connection(
                ("127.0.0.1", config["traffic"]["port"]), timeout=3
            ) as denied:
                denied.sendall(
                    b"CONNECT denied.fixture.test:443 HTTP/1.1\r\nHost: denied.fixture.test:443\r\n\r\n"
                )
                rejection = denied.recv(2048)
            if not rejection.startswith(b"HTTP/1.1 403"):
                raise LabError("Unapproved CONNECT host was not denied before upstream access")
            report["checks"]["unapprovedConnectDenied"] = True
            lab.traffic.stop()  # Flush all evidence before offline reading.
            capture = Path(startup["traffic"]["captureArtifact"])
            with capture.open("rb") as stream:
                matches = [
                    flow
                    for flow in io.FlowReader(stream).stream()
                    if flow.request.host == HOST
                    and flow.request.path == "/proof?nonce=" + nonce
                    and flow.response
                    and flow.response.status_code == 200
                    and flow.response.content == proof.encode()
                ]
            if len(matches) != 1:
                raise LabError(
                    "HTTPS UI proof did not correlate with exactly one decrypted capture"
                )
            report["checks"]["https"] = {
                "defaultSystemTrust": True,
                "upstreamTLSVerified": True,
                "fixtureHost": HOST,
                "statusCode": 200,
                "nonceCorrelated": True,
                "captureArtifact": str(capture),
            }
            # Verify the exact previous value, even if a caller's original proxy
            # coincidentally used this same endpoint.
            phase = "proxy restoration"
            expected_proxy = read_json(lab.proxy_record)["previous"]
            if expected_proxy in ("", ":0"):
                expected_proxy = "null"
            # Proxy restoration is checked while this known owned guest still runs.
            with android.lock():
                lab.restore_proxy()
                restored = lab.shell(["settings", "get", "global", "http_proxy"])
            report["checks"]["proxyRestored"] = restored == expected_proxy
            if not report["checks"]["proxyRestored"]:
                raise LabError("Owned proxy restoration failed")
            failed = False
    except (Exception, KeyboardInterrupt) as error:
        write_json(
            job / "failure.json",
            {"phase": phase, "error": str(error), "type": type(error).__name__},
        )
        if lab:
            try:
                code, diagnostic = lab.android.adb(["logcat", "-d", "-t", "100", "*:E"], 5)
                write_json(job / "guest-errors.json", {"exitCode": code, "log": diagnostic[:16384]})
            except Exception:
                pass
        if isinstance(error, LabError):
            raise LabError(f"Qualification {phase}: {error}", error.timeout) from error
        raise
    finally:
        original_error = sys.exc_info()[1]
        try:
            cleanup(lab, session, server, failed)
        except LabError as cleanup_error:
            if original_error:
                raise LabError(f"{original_error}; {cleanup_error}") from original_error
            raise
    # Restore default all-host capture without a stale TLS-origin mapping.
    report["lab"] = original.start()
    report["reportArtifact"] = str(job / "report.json")
    write_json(job / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(json.loads(args.config.read_text()), args.state_dir)))
    except (Exception, KeyboardInterrupt) as error:
        print(
            json.dumps(
                {
                    "status": "cancelled" if isinstance(error, KeyboardInterrupt) else "blocked",
                    "error": str(error) or "Qualification interrupted",
                }
            )
        )
        raise SystemExit(1)
