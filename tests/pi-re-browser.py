#!/usr/bin/env python3
"""Owned documentation-browser fixtures; set PI_RE_BROWSER_LIVE=1 for real local Chrome."""

import http.server
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "home-manager/modules/ai/pi-re"
sys.path.insert(0, str(CODE))
spec = importlib.util.spec_from_file_location("pi_re_browser", CODE / "browser.py")
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)

FAKE_CLI = r"""
import json, os, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
session = args[args.index("--sessionId") + 1]
command = args[args.index("--sessionId") + 2:]
scratch = Path(os.environ["HOME"]).parent
with (scratch / "calls.jsonl").open("a") as stream:
    stream.write(json.dumps({"command":command,"session":session,"env":dict(os.environ)}) + "\n")
if command[0] == "start":
    daemon = subprocess.Popen([sys.executable, str(Path(__file__).with_name("daemon.py"))],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        env=dict(os.environ, CHROME_DEVTOOLS_MCP_SESSION_ID=session))
    directory = Path(os.environ["XDG_RUNTIME_DIR"]) / ("chrome-devtools-mcp-" + session)
    directory.mkdir()
    if not Path(__file__).with_name("delayed").exists():
        (directory / "daemon.pid").write_text(str(daemon.pid))
    elif Path(__file__).with_name("empty").exists():
        (directory / "daemon.pid").touch()
    Path(__file__).with_name("startup.json").write_text(json.dumps({"pid":daemon.pid,"scratch":str(scratch)}))
    print("Started")
    if Path(__file__).with_name("failed-start").exists(): sys.exit(1)
elif command[0] == "new_page":
    if "fail.test" in command[1]: sys.exit(1)
    print(json.dumps({"pages":[{"id":7,"url":command[1],"selected":True}]}))
elif command[0] == "take_snapshot":
    output = next(value.removeprefix("--filePath=") for value in command if value.startswith("--filePath="))
    Path(output).write_text("DOCUMENTATION_BROWSER_MARKER")
    print(json.dumps({"snapshotFilePath":output}))
elif command[0] == "close_page":
    print(json.dumps({"pages":[]}))
else:
    raise RuntimeError("Unexpected browser command")
"""


class Browser(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pi-re-browser-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / "state"
        self.cli = self.root / "chrome-devtools"
        self.cli.write_text(f"#!{sys.executable}\n" + FAKE_CLI)
        self.cli.chmod(0o700)
        self.daemon = self.root / "daemon.py"
        self.daemon.write_text("import time\ntime.sleep(120)\n")
        self.config = {
            "browser": {
                "cli": str(self.cli),
                "executable": str(self.cli),
                "daemonScript": str(self.daemon),
            }
        }
        self.environment = patch.dict(
            os.environ,
            {"PROVIDER_TOKEN": "BROWSER_SECRET_CANARY", "HERDR_SOCKET_PATH": "FOREIGN_SOCKET"},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        for key in ("PI_RE_CHILD", "PI_RE_RESEARCH"):
            os.environ.pop(key, None)

    def test_documentation_read_uses_fresh_namespace_private_profile_and_pidfd_cleanup(self):
        calls = []
        original = browser.cli_call

        def capture(cli, session, args, env, **kwargs):
            calls.append((session, args, env))
            return original(cli, session, args, env, **kwargs)

        with patch.object(browser, "cli_call", side_effect=capture):
            result = browser.read_page(self.config, self.state, "https://docs.example.test/manual")
        self.assertEqual(result["snapshot"], "DOCUMENTATION_BROWSER_MARKER")
        self.assertTrue(result["cleanupComplete"])
        self.assertEqual(
            [args[0] for _, args, _ in calls], ["start", "new_page", "take_snapshot", "close_page"]
        )
        self.assertTrue(all(session == result["session"] for session, _, _ in calls))
        self.assertNotIn("BROWSER_SECRET_CANARY", json.dumps(calls))
        self.assertNotIn("FOREIGN_SOCKET", json.dumps(calls))
        start = calls[0][1]
        for flag in (
            "--usageStatistics=false",
            "--performanceCrux=false",
            "--javascriptEvaluation=false",
            "--categoryInput=false",
            "--categoryNetwork=false",
        ):
            self.assertIn(flag, start)
        self.assertFalse(
            any(
                "autoConnect" in argument or "browserUrl" in argument or "wsEndpoint" in argument
                for argument in start
            )
        )
        owner = json.loads((Path(result["artifact"]) / "owner.json").read_text())
        self.assertFalse(Path(owner["scratch"]).exists())
        self.assertNotEqual(browser.process_identity(owner["daemon"]["pid"]), owner["daemon"])

    def test_late_startup_failure_recovers_and_cleans_its_owned_namespace(self):
        original = browser.cli_call

        def interrupted(cli, session, arguments, environment, **kwargs):
            result = original(cli, session, arguments, environment, **kwargs)
            if arguments[0] == "start":
                raise browser.BrowserError("Fixture cancellation after daemon startup")
            return result

        with patch.object(browser, "cli_call", side_effect=interrupted):
            with self.assertRaisesRegex(browser.BrowserError, "read failed"):
                browser.read_page(self.config, self.state, "https://docs.example.test")
        cleanup = next((self.state / "browser").glob("*/cleanup.json"))
        self.assertTrue(json.loads(cleanup.read_text())["complete"])

    def test_cancellation_before_pid_publication_reconciles_owned_startup(self):
        self.check_incomplete_publication(initially_empty=False)

    def test_empty_then_populated_pid_file_reconciles_owned_startup(self):
        self.check_incomplete_publication(initially_empty=True)

    def check_incomplete_publication(self, *, initially_empty):
        (self.root / "delayed").touch()
        if initially_empty:
            (self.root / "empty").touch()
        self.daemon.write_text(
            "import os,time\nfrom pathlib import Path\ntime.sleep(0.4)\n"
            "p=Path(os.environ['XDG_RUNTIME_DIR'])/('chrome-devtools-mcp-'+os.environ['CHROME_DEVTOOLS_MCP_SESSION_ID'])/'daemon.pid'\n"
            "p.write_text(str(os.getpid()))\ntime.sleep(120)\n"
        )
        original = browser.cli_call

        def interrupted(cli, session, arguments, environment, **kwargs):
            result = original(cli, session, arguments, environment, **kwargs)
            if arguments[0] == "start":
                pid_file = (
                    Path(environment["XDG_RUNTIME_DIR"])
                    / ("chrome-devtools-mcp-" + session)
                    / "daemon.pid"
                )
                self.assertEqual(pid_file.exists(), initially_empty)
                if initially_empty:
                    self.assertEqual(pid_file.read_text(), "")
                raise browser.BrowserError("Fixture cancellation before PID publication")
            return result

        with patch.object(browser, "cli_call", side_effect=interrupted):
            with self.assertRaisesRegex(browser.BrowserError, "read failed"):
                browser.read_page(self.config, self.state, "https://docs.example.test")
        cleanup = next((self.state / "browser").glob("*/cleanup.json"))
        record = json.loads(cleanup.read_text())
        self.assertTrue(record["complete"])
        self.assertFalse(Path(record["scratch"]).exists())

    def test_first_signal_during_startup_reconciliation_cannot_interrupt_retirement(self):
        (self.root / "delayed").touch()
        (self.root / "failed-start").touch()
        self.daemon.write_text(
            "import os,time\nfrom pathlib import Path\ntime.sleep(1)\n"
            "p=Path(os.environ['XDG_RUNTIME_DIR'])/('chrome-devtools-mcp-'+os.environ['CHROME_DEVTOOLS_MCP_SESSION_ID'])/'daemon.pid'\n"
            "p.write_text(str(os.getpid()))\ntime.sleep(120)\n"
        )
        runtime = self.root / "runtime.json"
        runtime.write_text(json.dumps(self.config))
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(CODE / "browser.py"),
                "--config",
                str(runtime),
                "--state-dir",
                str(self.state),
                "read",
                "https://docs.example.test",
                "--json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if (self.root / "startup.json").exists():
                    # Startup command has failed and the helper is now sleeping
                    # in its bounded reconciliation loop, not the CLI poll loop.
                    waiting = Path(f"/proc/{process.pid}/wchan").read_text()
                    if "nanosleep" in waiting:
                        break
                time.sleep(0.01)
            else:
                self.fail("Browser did not enter startup reconciliation")
            process.send_signal(signal.SIGTERM)
            _, diagnostics = process.communicate(timeout=8)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("read failed", diagnostics.decode())
            owner = json.loads((self.root / "startup.json").read_text())
            self.assertIsNone(browser.process_identity(owner["pid"]))
            cleanup = next((self.state / "browser").glob("*/cleanup.json"))
            self.assertTrue(json.loads(cleanup.read_text())["complete"])
            self.assertFalse(Path(owner["scratch"]).exists())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            for stream in (process.stdout, process.stderr):
                stream.close()

    def test_recording_failure_cannot_bypass_owned_daemon_cleanup(self):
        original_call = browser.cli_call
        original_acquire = browser.acquire_daemon
        owners = []

        def interrupted(cli, session, arguments, environment, **kwargs):
            result = original_call(cli, session, arguments, environment, **kwargs)
            if arguments[0] == "start":
                raise browser.BrowserError("Fixture cancellation after daemon fork")
            return result

        def acquired(*arguments):
            value = original_acquire(*arguments)
            owners.append(value[0])
            return value

        with (
            patch.object(browser, "cli_call", side_effect=interrupted),
            patch.object(browser, "acquire_daemon", side_effect=acquired),
            patch.object(browser, "write_private", side_effect=OSError("Fixture quota exhausted")),
        ):
            with self.assertRaisesRegex(
                browser.BrowserError, "read failed.*artifact recording failed"
            ):
                browser.read_page(self.config, self.state, "https://docs.example.test")
        self.assertTrue(owners)
        self.assertIsNone(browser.process_identity(owners[-1]["pid"]))

    def test_navigation_failure_still_cleans_only_its_owned_daemon(self):
        with self.assertRaisesRegex(browser.BrowserError, "read failed"):
            browser.read_page(self.config, self.state, "https://fail.test/manual")
        cleanup = next((self.state / "browser").glob("*/cleanup.json"))
        self.assertTrue(json.loads(cleanup.read_text())["complete"])

    def test_private_url_and_child_lifecycle_requests_are_rejected(self):
        for url in (
            "file:///etc/passwd",
            "javascript:alert(1)",
            "https://user:secret@example.test",
            "not-a-url",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                browser.read_page(self.config, self.state, url)
        with (
            patch.dict(os.environ, {"PI_RE_RESEARCH": "1"}),
            self.assertRaisesRegex(ValueError, "root-only"),
        ):
            browser.read_page(self.config, self.state, "https://docs.example.test")
        self.assertFalse(self.state.exists())

    @unittest.skipUnless(
        os.environ.get("PI_RE_BROWSER_LIVE") == "1", "opt-in real local Chrome fixture"
    )
    def test_real_owned_browser_reads_javascript_rendered_loopback_documentation(self):
        observed = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                observed.append(dict(self.headers))
                body = b"<html><title>Owned documentation</title><body><script>document.body.append('LIVE_DOC_BROWSER_MARKER');</script></body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        cli = Path(shutil.which("chrome-devtools")).resolve()
        package = cli.parent.parent
        config = {
            "browser": {
                "cli": str(cli),
                "executable": str(Path(shutil.which("google-chrome-stable")).absolute()),
                "daemonScript": str(
                    package
                    / "lib/chrome-devtools-mcp/node_modules/chrome-devtools-mcp/build/src/daemon/daemon.js"
                ),
            }
        }
        url = f"http://127.0.0.1:{server.server_port}/manual"
        if os.environ.get("PI_RE_BROWSER_BIN"):
            environment = dict(
                os.environ,
                HOME=str(self.root / "home"),
                XDG_STATE_HOME=str(self.root / "caller-state"),
                XDG_DATA_HOME=str(self.root / "caller-data"),
            )
            command = subprocess.run(
                [os.environ["PI_RE_BROWSER_BIN"], "browser", "read", url, "--json"],
                env=environment,
                capture_output=True,
                text=True,
                timeout=90,
            )
            self.assertEqual(command.returncode, 0, command.stderr)
            result = json.loads(command.stdout)
        else:
            result = browser.read_page(config, self.state, url)
        self.assertTrue(result["cleanupComplete"])
        self.assertIn("LIVE_DOC_BROWSER_MARKER", result["snapshot"])
        self.assertTrue(observed)
        self.assertTrue(
            all("Authorization" not in headers and "Cookie" not in headers for headers in observed)
        )


if __name__ == "__main__":
    unittest.main()
