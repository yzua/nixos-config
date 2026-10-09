#!/usr/bin/env python3
"""Exercise extension tools through installed Pi without paid model calls.

Run: python3 tests/pi-extensions.py
Pi supplies the extension API and loader. Web dependencies come from the installed
extension (override PI_WEB_FETCH_DIR); the TypeScript under test comes from Git.
HTTP fixtures, sessions, and settings are private and temporary.
"""

import gzip
import http.server
import json
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_test_support import isolated_environment, require_pi, require_web_fetch_dependencies

REPO = Path(__file__).resolve().parents[1]
EXTENSIONS = REPO / "home-manager/modules/ai/pi/extensions"
TEXT_LIMIT = 5 * 1024 * 1024
PDF_LIMIT = 20 * 1024 * 1024


def pdf_fixture(padding=0):
    content = b"BT /F1 16 Tf 72 720 Td (PI_PDF_MARKER: PDF extraction works.) Tj ET"
    content += b" " * padding
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
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def send_body(self, content_type, body, transport="length"):
        transfer = self.server.transfers.get(self.path)
        self.send_header("Content-Type", content_type)
        if transport.startswith("gzip-"):
            body = gzip.compress(body)
            self.send_header("Content-Encoding", "gzip")
            transport = transport.removeprefix("gzip-")
        if transport == "length":
            self.send_header("Content-Length", str(len(body)))
        elif transport == "chunked":
            self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        try:
            for offset in range(0, len(body), 64 * 1024):
                chunk = body[offset : offset + 64 * 1024]
                if transport == "chunked":
                    self.wfile.write(f"{len(chunk):x}\r\n".encode())
                self.wfile.write(chunk)
                if transport == "chunked":
                    self.wfile.write(b"\r\n")
                if transfer is not None:
                    transfer["sent"] += len(chunk)
            if transport == "chunked":
                self.wfile.write(b"0\r\n\r\n")
        except (BrokenPipeError, ConnectionResetError):
            if transfer is not None:
                transfer["cancelled"] = True
        finally:
            if transfer is not None:
                transfer["finished"].set()

    def do_GET(self):
        if self.path.startswith("/bounds/"):
            _, _, kind, transport, boundary = self.path.split("/")
            limit = PDF_LIMIT if kind == "pdf" else TEXT_LIMIT
            size = {
                "below": limit - 1,
                "exact": limit,
                "over": limit + 1,
                "cancel": 32 * 1024 * 1024,
            }[boundary]
            if kind == "pdf":
                padding = size - len(pdf_fixture())
                body = pdf_fixture(padding)
                body = pdf_fixture(padding - (len(body) - size))
                content_type = "application/pdf"
            else:
                # UTF-8 proves the bound counts bytes, not decoded characters.
                body = b"\xc3\xa9" * (size // 2) + b"x" * (size % 2)
                content_type = "text/plain"
            assert len(body) == size
            self.send_response(200)
            self.send_body(content_type, body, transport)
            return
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/article")
            self.send_header("Content-Length", "0")
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
            "/large-no-length": ("text/plain", b"x" * (5 * 1024 * 1024 + 1)),
        }.get(self.path)
        self.send_response(200 if response else 404)
        content_type, body = response or ("text/plain", b"Not found")
        self.send_body(
            content_type, body, "no-length" if self.path == "/large-no-length" else "length"
        )


class Extensions(unittest.TestCase):
    def setUp(self):
        self.pi = require_pi()
        dependencies = require_web_fetch_dependencies()
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
        (self.web / "node_modules").symlink_to(dependencies / "node_modules")
        self.env = isolated_environment()
        self.env["PI_CODING_AGENT_DIR"] = str(agent)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fixtures)
        self.server.transfers = {}
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def command(self, extension, mode):
        return [
            self.pi,
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

    def check_fetch_before_exit(self, path, check):
        # Keep Pi alive during the check: process exit must not masquerade as cancellation.
        fixture = self.root / "case.json"
        fixture.write_text(
            json.dumps({"tool": "web_fetch", "arguments": {"url": self.base + path}})
        )
        process = subprocess.Popen(
            self.command(self.web / "index.ts", "rpc"),
            cwd=self.root,
            env=dict(self.env, PI_EXTENSION_CASE=str(fixture)),
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
        try:
            process.stdin.write(
                json.dumps({"type": "prompt", "message": "Run the tool fixture"}) + "\n"
            )
            process.stdin.flush()
            deadline = time.monotonic() + 20
            while True:
                event = events.get(timeout=max(0.001, deadline - time.monotonic()))
                if event["type"] == "tool_execution_end":
                    self.assertEqual(event["toolName"], "web_fetch")
                    check(event)
                    self.assertIsNone(process.poll(), "Pi exited before the cancellation check")
                    break
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

    def test_web_rejects_overflow_without_content_length(self):
        result = self.fetch("/large-no-length")
        self.assert_size_error(result)

    def assert_size_error(self, result):
        self.assertTrue(result["isError"], "Oversize response was accepted")
        error = json.dumps(result["result"])
        self.assertIn("Response too large", error)
        self.assertNotIn("Chrome DevTools CLI", error)

    def test_web_rejects_chunked_and_decompressed_overflow(self):
        for transport in ["chunked", "gzip-length", "gzip-chunked"]:
            with self.subTest(transport=transport):
                self.assert_size_error(self.fetch(f"/bounds/text/{transport}/over"))

    def test_web_accepts_byte_exact_limits(self):
        for transport, boundary in [
            ("no-length", "below"),
            ("no-length", "exact"),
            ("chunked", "exact"),
            ("length", "exact"),
            ("gzip-length", "exact"),
        ]:
            with self.subTest(transport=transport, boundary=boundary):
                result = self.fetch(f"/bounds/text/{transport}/{boundary}")
                self.assertFalse(result["isError"], "Response within the byte limit was rejected")
                chars = result["result"]["details"]["chars"]
                self.assertEqual(chars, 2621440)
                text = result["result"]["content"][0]["text"]
                self.assertTrue(text.endswith("x" if boundary == "below" else "é"))
                self.assertNotIn("�", text)

    def test_web_cancels_oversize_streams_and_known_lengths(self):
        for transport in ["chunked", "length"]:
            with self.subTest(transport=transport):
                path = f"/bounds/text/{transport}/cancel"
                transfer = {"finished": threading.Event(), "sent": 0, "cancelled": False}
                self.server.transfers[path] = transfer

                def check(result):
                    self.assert_size_error(result)
                    self.assertTrue(
                        transfer["finished"].wait(timeout=5), "HTTP fixture did not finish"
                    )
                    self.assertTrue(
                        transfer["cancelled"], "Rejected response was drained, not cancelled"
                    )
                    self.assertLess(transfer["sent"], 32 * 1024 * 1024)

                self.check_fetch_before_exit(path, check)

    def test_web_keeps_size_error_when_cancellation_rejects(self):
        # A synthetic fetch boundary is needed: native HTTP cancellation rarely rejects.
        extension = self.web / "cancel-rejection.ts"
        extension.write_text(
            """
import registerWebFetch from "./index.ts";
import { writeFileSync } from "node:fs";
export default function (pi) {
  globalThis.fetch = async (url) => {
    const knownLength = new URL(url).pathname === "/known-length";
    const headers = { "Content-Type": "text/plain" };
    if (knownLength) headers["Content-Length"] = String(5 * 1024 * 1024 + 1);
    return new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(new Uint8Array(5 * 1024 * 1024));
        controller.enqueue(new Uint8Array(1));
      },
      cancel() {
        writeFileSync(process.env.PI_WEB_FETCH_CANCEL_LOG, "cancelled");
        throw new Error("PI_CANCEL_FAILURE");
      },
    }), { headers });
  };
  registerWebFetch(pi);
}
"""
        )
        log = self.root / "cancelled"
        self.env["PI_WEB_FETCH_CANCEL_LOG"] = str(log)
        for path in ["/stream", "/known-length"]:
            with self.subTest(path=path):
                log.unlink(missing_ok=True)
                result = self.call("web_fetch", {"url": self.base + path}, extension)
                self.assert_size_error(result)
                self.assertNotIn("PI_CANCEL_FAILURE", json.dumps(result["result"]))
                self.assertEqual(log.read_text(), "cancelled")

    def test_pdf_has_its_own_decompressed_byte_limit(self):
        for transport in ["no-length", "chunked", "gzip-length", "length"]:
            with self.subTest(transport=transport):
                result = self.fetch(f"/bounds/pdf/{transport}/exact")
                self.assertFalse(result["isError"], result)
                self.assertIn("PI_PDF_MARKER", json.dumps(result["result"]))
                self.assert_size_error(self.fetch(f"/bounds/pdf/{transport}/over"))

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
