#!/usr/bin/env python3
"""Exercise extension tools through installed Pi without paid model calls.

Run: python3 tests/pi-extensions.py
Pi supplies the extension API and loader. Web dependencies come from the installed
extension (override PI_WEB_FETCH_DIR); the TypeScript under test comes from Git.
HTTP fixtures, sessions, and settings are private and temporary.
"""

import http.server
import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXTENSIONS = REPO / "home-manager/modules/ai/pi/extensions"
PI = os.environ.get("PI_BIN", shutil.which("pi"))
DEPENDENCIES = Path(
    os.environ.get("PI_WEB_FETCH_DIR", Path.home() / ".pi/agent/extensions/web-fetch")
)


def pdf_fixture():
    content = b"BT /F1 16 Tf 72 720 Td (PI_PDF_MARKER: PDF extraction works.) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    result = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(result)
    result += b"xref\n0 6\n0000000000 65535 f \n"
    result += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    result += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return result


class Fixtures(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/article")
            self.end_headers()
            return
        article = (
            "<html><head><title>Pi fixture article</title></head><body><article><h1>Pi fixture</h1>"
            "<p>"
            + "PI_HTML_MARKER. This article explains integration testing. " * 40
            + "</p></article></body></html>"
        ).encode()
        response = {
            "/article": ("text/html", article),
            "/text": ("text/plain", b"PI_TEXT_MARKER. Plain text fixture."),
            "/markdown": ("text/markdown", b"# PI_MARKDOWN_MARKER\nMarkdown fixture."),
            "/json": ("application/json", b'{"marker":"PI_JSON_MARKER"}'),
            "/sample.pdf": ("application/pdf", pdf_fixture()),
            "/binary": ("application/octet-stream", b"Binary fixture"),
            "/large": ("text/plain", b"x" * (6 * 1024 * 1024)),
        }.get(self.path)
        self.send_response(200 if response else 404)
        content_type, body = response or ("text/plain", b"Not found")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class Extensions(unittest.TestCase):
    def setUp(self):
        if not PI:
            self.fail("Pi is required; install it or set PI_BIN")
        if not (DEPENDENCIES / "node_modules").is_dir():
            self.fail("Install web-fetch dependencies or set PI_WEB_FETCH_DIR")
        temporary = tempfile.TemporaryDirectory(prefix="pi-extensions-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        agent = self.root / "agent"
        agent.mkdir()
        (agent / "settings.json").write_text(
            json.dumps({"retry": {"enabled": False}, "compaction": {"enabled": False}})
        )
        self.web = self.root / "web-fetch"
        self.web.mkdir()
        shutil.copy2(EXTENSIONS / "web-fetch/index.ts", self.web / "index.ts")
        shutil.copy2(EXTENSIONS / "web-fetch/package.json", self.web / "package.json")
        (self.web / "node_modules").symlink_to(DEPENDENCIES / "node_modules")
        self.env = dict(os.environ, PI_CODING_AGENT_DIR=str(agent))
        for key in tuple(self.env):
            if key.startswith("PI_SUBAGENT") or key in {"TMUX", "TMUX_PANE"}:
                self.env.pop(key)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fixtures)
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def command(self, extension, mode):
        return [
            PI,
            "--offline",
            "--no-extensions",
            "--no-context-files",
            "--no-skills",
            "--no-prompt-templates",
            "--no-session",
            "--mode",
            mode,
            "--model",
            "extension-test/offline",
            "-e",
            str(REPO / "tests/pi-extensions/provider.ts"),
            "-e",
            str(extension),
        ]

    def call(self, tool, arguments, extension):
        fixture = self.root / "case.json"
        fixture.write_text(json.dumps({"tool": tool, "arguments": arguments}))
        result = subprocess.run(
            self.command(extension, "json") + ["--print", "Run the tool fixture"],
            cwd=self.root,
            env=dict(self.env, PI_EXTENSION_CASE=str(fixture)),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        outputs = [
            e for e in events if e.get("type") == "tool_execution_end" and e.get("toolName") == tool
        ]
        self.assertEqual(len(outputs), 1, result.stdout + result.stderr)
        return outputs[0]

    def fetch(self, path):
        return self.call("web_fetch", {"url": self.base + path}, self.web / "index.ts")

    def test_pdf_uses_packaged_pdfjs_through_pi_loader(self):
        result = self.fetch("/sample.pdf")
        self.assertFalse(result["isError"], result)
        self.assertIn("PI_PDF_MARKER", json.dumps(result["result"]))

    def test_supported_web_content_and_redirect(self):
        for path, marker in [
            ("/article", "PI_HTML_MARKER"),
            ("/text", "PI_TEXT_MARKER"),
            ("/markdown", "PI_MARKDOWN_MARKER"),
            ("/json", "PI_JSON_MARKER"),
            ("/redirect", "PI_HTML_MARKER"),
        ]:
            with self.subTest(path=path):
                result = self.fetch(path)
                self.assertFalse(result["isError"], result)
                text = "\n".join(c.get("text", "") for c in result["result"]["content"])
                self.assertIn(marker, text.replace("\\_", "_"))

    def test_invalid_binary_large_and_missing_responses(self):
        for url, marker in [
            ("not a URL", "Invalid URL"),
            (self.base + "/binary", "Unsupported content type"),
            (self.base + "/large", "Response too large"),
            (self.base + "/missing", "Chrome DevTools CLI"),
        ]:
            with self.subTest(url=url):
                result = self.call("web_fetch", {"url": url}, self.web / "index.ts")
                self.assertTrue(result["isError"], result)
                self.assertIn(marker, json.dumps(result["result"]))

    def test_question_requires_ui_in_print_mode(self):
        for extra in [{}, {"options": [{"label": "Alpha"}]}, {"multiSelect": True}]:
            with self.subTest(extra=extra):
                result = self.call(
                    "ask_user_question",
                    {"question": "Fixture question", **extra},
                    EXTENSIONS / "ask-user-question.ts",
                )
                self.assertFalse(result["isError"], result)
                self.assertEqual(result["result"]["details"]["status"], "unavailable")

    def test_question_balances_waiting_events_on_answer_and_cancel(self):
        for cancel in [False, True]:
            with self.subTest(cancel=cancel):
                fixture = self.root / "case.json"
                fixture.write_text(
                    json.dumps({"tool": "ask_user_question", "arguments": {"question": "Fixture"}})
                )
                event_log = self.root / "waiting.jsonl"
                event_log.unlink(missing_ok=True)
                process = subprocess.Popen(
                    self.command(EXTENSIONS / "ask-user-question.ts", "rpc"),
                    cwd=self.root,
                    env=dict(
                        self.env,
                        PI_EXTENSION_CASE=str(fixture),
                        PI_EXTENSION_EVENTS=str(event_log),
                    ),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
                events = queue.Queue()

                def read_events():
                    for line in process.stdout:
                        events.put(json.loads(line))

                reader = threading.Thread(target=read_events, daemon=True)
                reader.start()

                def send(value):
                    process.stdin.write(json.dumps(value) + "\n")
                    process.stdin.flush()

                try:
                    send({"type": "prompt", "message": "Run the tool fixture"})
                    deadline = time.monotonic() + 15
                    output = None
                    while True:
                        event = events.get(timeout=max(0.001, deadline - time.monotonic()))
                        if event["type"] == "extension_ui_request":
                            self.assertEqual(event["method"], "editor")
                            waiting = [
                                json.loads(line) for line in event_log.read_text().splitlines()
                            ]
                            self.assertEqual(waiting, [{"active": True, "label": "Fixture"}])
                            response = {"type": "extension_ui_response", "id": event["id"]}
                            response.update({"cancelled": True} if cancel else {"value": "Answer"})
                            send(response)
                        elif event["type"] == "tool_execution_end":
                            output = event
                        elif event["type"] == "agent_settled":
                            break
                    self.assertIsNotNone(output)
                    self.assertFalse(output["isError"], output)
                    self.assertEqual(
                        output["result"]["details"]["status"], "cancelled" if cancel else "answered"
                    )
                    waiting = [json.loads(line) for line in event_log.read_text().splitlines()]
                    self.assertEqual(
                        waiting, [{"active": True, "label": "Fixture"}, {"active": False}]
                    )
                finally:
                    process.stdin.close()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    reader.join(timeout=1)
                    process.stdout.close()
                    process.stderr.close()

    def test_safe_bash_executes_and_blocks_harmless_pattern_probes(self):
        extension = EXTENSIONS / "interactive-subagents/pi-extension/subagents/tools/safe-bash.ts"
        result = self.call("safe_bash", {"command": "printf PI_SAFE_BASH_OK"}, extension)
        self.assertFalse(result["isError"], result)
        self.assertIn("PI_SAFE_BASH_OK", json.dumps(result["result"]))
        # Quoted text is harmless even if the blocklist regresses.
        for text in ["sudo echo fixture", "reboot", "mkfs", "rm -rf /"]:
            with self.subTest(text=text):
                result = self.call("safe_bash", {"command": f"printf '%s' '{text}'"}, extension)
                self.assertTrue(result["isError"], result)
                self.assertIn("Command blocked by safe_bash", json.dumps(result["result"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
