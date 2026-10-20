#!/usr/bin/env python3
"""Native search fixtures through Pi's loader; no live credentials or paid calls."""

import http.server
import json
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_test_support import isolated_environment, require_pi

REPO = Path(__file__).resolve().parents[1]
EXTENSION = REPO / "home-manager/modules/ai/pi-base/extensions/web-search/index.ts"
TOKEN = "PI_SEARCH_PRIVATE_TOKEN"


class SearchFixtures(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(
            (self.path, {k.lower(): v for k, v in self.headers.items()}, body)
        )
        self.server.started.set()
        query = body["commands"]["search_query"][0]["q"]
        if query == "slow-body":
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"output":"')
                self.wfile.flush()
                self.server.body_started.set()
                self.server.release.wait(timeout=40)
                self.wfile.write(b'late result"}')
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        status = {"unauthorized": 401, "quota": 429, "unsupported": 404}.get(query, 200)
        if query == "redirect":
            self.send_response(307)
            self.send_header("Location", self.server.redirect_url)
            self.end_headers()
            return
        payload = {
            "output": "Search summary",
            "encrypted_output": TOKEN,
            "results": [
                {
                    "type": "text_result",
                    "title": f"Source {i}",
                    "url": f"https://example.org/source/{i}",
                    "snippet": "Fixture search evidence",
                }
                for i in range(12)
            ],
        }
        if query == "empty":
            payload = {"output": "", "results": []}
        elif query == "legacy":
            payload = {"output": "Legacy result https://example.org/legacy"}
        elif query == "malformed":
            payload = {"output": 3, "results": []}
        elif query == "invalid-results":
            payload = {"output": "summary", "results": {"private": TOKEN}}
        elif query == "unknown-results":
            payload["results"] = [
                {"type": "future_result", "private": TOKEN},
                {"type": "text_result", "url": "javascript:alert(1)"},
                {"type": "text_result", "url": "https://secret@example.org/"},
                {"type": "text_result", "url": "https://example.org/" + "x" * 2100},
            ] + payload["results"]
        elif query == "long-output":
            payload = {"output": "é" * (40 * 1024), "results": []}
        elif query == "slow":
            self.server.release.wait(timeout=40)
        if status != 200:
            payload = {"error": {"message": TOKEN}}
        raw = json.dumps(payload).encode()
        if query == "invalid-json":
            raw = TOKEN.encode()
        elif query == "oversized":
            raw = b"x" * (1024 * 1024 + 1)
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass


class NativeSearch(unittest.TestCase):
    def setUp(self):
        self.pi = require_pi()
        temporary = tempfile.TemporaryDirectory(prefix="pi-web-search-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        agent = self.root / "agent"
        agent.mkdir()
        (agent / "settings.json").write_text(
            json.dumps({"retry": {"enabled": False}, "compaction": {"enabled": False}})
        )
        self.env = dict(isolated_environment(), PI_CODING_AGENT_DIR=str(agent))
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SearchFixtures)
        self.server.requests = []
        self.server.started = threading.Event()
        self.server.body_started = threading.Event()
        self.server.release = threading.Event()
        self.server.redirect_url = f"http://127.0.0.1:{self.server.server_port}/leaked"
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.release.set)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def command(
        self,
        query,
        *,
        arguments=None,
        api="openai-responses",
        base=None,
        extension=EXTENSION,
        **fixture,
    ):
        case = self.root / "case.json"
        case.write_text(
            json.dumps(
                {
                    "tool": "web_search",
                    "arguments": arguments or {"query": query},
                    "api": api,
                    "apiKey": TOKEN,
                    "baseUrl": base or self.base + "/v1",
                    **fixture,
                }
            )
        )
        return [
            self.pi,
            "--offline",
            "--no-extensions",
            "--no-context-files",
            "--no-skills",
            "--no-prompt-templates",
            "--no-session",
            "--model",
            "extension-test/offline",
            "-e",
            str(REPO / "tests/pi-extensions/provider.ts"),
            "-e",
            str(extension),
        ], dict(self.env, PI_EXTENSION_CASE=str(case))

    def call(self, query="fixture", *, cli_key=None, **kwargs):
        args, env = self.command(query, **kwargs)
        if cli_key:
            args += ["--api-key", cli_key]
        result = subprocess.run(
            args + ["--mode", "json", "--print", "Run the tool fixture"],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=40,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        outputs = [
            json.loads(line)
            for line in result.stdout.splitlines()
            if line.startswith("{") and json.loads(line).get("type") == "tool_execution_end"
        ]
        self.assertEqual(len(outputs), 1, result.stdout + result.stderr)
        self.assertEqual(outputs[0]["toolName"], "web_search")
        return outputs[0]

    def test_request_authentication_query_privacy_and_result_limit(self):
        result = self.call(arguments={"query": "fixture", "limit": 2, "recency_days": 7})
        self.assertFalse(result["isError"], result)
        path, headers, payload = self.server.requests[0]
        self.assertEqual(path, "/backend-api/codex/alpha/search")
        self.assertEqual(headers["authorization"], "Bearer " + TOKEN)
        self.assertEqual(payload["model"], "offline")
        self.assertNotIn("input", payload, "Conversation history must not be transmitted")
        self.assertEqual(payload["commands"]["search_query"], [{"q": "fixture", "recency": 7}])
        self.assertTrue(payload["settings"]["external_web_access"])
        self.assertEqual(len(result["result"]["details"]["results"]), 2)
        self.assertIn("https://example.org/source/0", json.dumps(result["result"]))
        self.assertEqual(
            result["result"]["structuredContent"]["results"], result["result"]["details"]["results"]
        )

    def test_endpoint_paths_and_header_precedence(self):
        for path in ["/v1/", "/backend-api/codex/", "/gateway/v1"]:
            with self.subTest(path=path):
                result = self.call(
                    base=self.base + path,
                    headers={"X-Fixture": "resolved", "Authorization": "Bearer fixture-override"},
                    modelHeaders={"X-Fixture": "model", "X-Model": "kept"},
                )
                self.assertFalse(result["isError"], result)
                endpoint, headers, _ = self.server.requests[-1]
                prefix = "/gateway" if path.startswith("/gateway") else ""
                self.assertEqual(endpoint, prefix + "/backend-api/codex/alpha/search")
                self.assertEqual(headers["authorization"], "Bearer fixture-override")
                self.assertEqual(headers["x-fixture"], "model")
                self.assertEqual(headers["x-model"], "kept")

    def configured_extension(self, config):
        directory = self.root / "configured-search"
        directory.mkdir(exist_ok=True)
        (directory / "index.ts").write_text(EXTENSION.read_text())
        (directory / "config.json").write_text(json.dumps(config))
        return directory / "index.ts"

    def test_non_responses_chat_uses_separate_search_backend_and_credentials(self):
        extension = self.configured_extension({"provider": "search-test", "model": "search-model"})
        result = self.call(
            api="extension-test-api",
            extension=extension,
            cli_key="CHAT_KEY_MUST_NOT_REACH_SEARCH",
            searchProvider={"baseUrl": self.base + "/v1", "apiKey": TOKEN},
        )
        self.assertFalse(result["isError"], result)
        _, headers, payload = self.server.requests[0]
        self.assertEqual(headers["authorization"], "Bearer " + TOKEN)
        self.assertEqual(payload["model"], "search-model")
        self.assertNotIn("CHAT_KEY_MUST_NOT_REACH_SEARCH", json.dumps(self.server.requests))

    def test_missing_configured_model_fails_without_fallback_or_network(self):
        extension = self.configured_extension({"provider": "missing", "model": "missing"})
        result = self.call(extension=extension)
        self.assertTrue(result["isError"], result)
        self.assertIn("configured search model is unavailable", json.dumps(result["result"]))
        self.assertEqual(self.server.requests, [])

    def test_auth_resolution_failure_and_exception_are_sanitized(self):
        wrapper = self.root / "auth-error.ts"
        for throws in [False, True]:
            with self.subTest(throws=throws):
                action = (
                    f'throw new Error("{TOKEN}")'
                    if throws
                    else f'return {{ ok: false, error: "{TOKEN}" }}'
                )
                wrapper.write_text(
                    f"import registerSearch from {json.dumps(str(EXTENSION))};\n"
                    "export default function (pi) {\n"
                    "  registerSearch({ registerTool(tool) {\n"
                    "    pi.registerTool({ ...tool, async execute(id, args, signal, update, ctx) {\n"
                    "      const context = { ...ctx, modelRegistry: {\n"
                    f"        async getApiKeyAndHeaders() {{ {action}; }}\n"
                    "      }};\n"
                    "      return tool.execute(id, args, signal, update, context);\n"
                    "    }});\n"
                    "  }});\n"
                    "}\n"
                )
                result = self.call(extension=wrapper)
                self.assertTrue(result["isError"], result)
                self.assertIn("authentication", json.dumps(result["result"]))
        self.assertEqual(self.server.requests, [])

    def test_runtime_api_key_takes_precedence(self):
        result = self.call(cli_key="fixture-runtime-key")
        self.assertFalse(result["isError"], result)
        self.assertEqual(self.server.requests[0][1]["authorization"], "Bearer fixture-runtime-key")

    def test_timeout_is_a_tool_error(self):
        result = self.call("slow")
        self.assertTrue(result["isError"], result)
        self.assertIn("timed out after 30 seconds", json.dumps(result["result"]))

    def test_schema_provider_and_endpoint_rejections_do_not_send_requests(self):
        cases = [
            {"arguments": {"query": " "}},
            {"arguments": {"query": "fixture", "limit": 11}},
            {"arguments": {"query": "fixture", "recency_days": -1}},
            {"api": "extension-test-api"},
            {"base": self.base + "/unsupported"},
            {"base": self.base + "/v1?token=private"},
            {"base": "file:///v1"},
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertTrue(self.call(**case)["isError"])
        self.assertEqual(self.server.requests, [])

    def test_errors_are_sanitized_and_redirects_do_not_forward_auth(self):
        for query, message in [
            ("unauthorized", "HTTP 401"),
            ("quota", "HTTP 429"),
            ("unsupported", "HTTP 404"),
            ("redirect", "redirect"),
            ("malformed", "invalid response"),
            ("invalid-results", "invalid results"),
            ("invalid-json", "invalid JSON"),
            ("oversized", "1 MiB"),
        ]:
            with self.subTest(query=query):
                result = self.call(query)
                self.assertTrue(result["isError"], result)
                self.assertIn(message, json.dumps(result["result"]))
        self.assertFalse(any(path == "/leaked" for path, _, _ in self.server.requests))

    def test_empty_legacy_unknown_variants_and_bounded_output(self):
        for query, marker in [
            ("empty", "No search results found"),
            ("legacy", "https://example.org/legacy"),
            ("unknown-results", "https://example.org/source/0"),
            ("long-output", "Search output truncated"),
        ]:
            with self.subTest(query=query):
                result = self.call(query)
                self.assertFalse(result["isError"], result)
                text = result["result"]["content"][0]["text"]
                self.assertIn(marker, text)
                self.assertLessEqual(len(text.encode()), 33 * 1024)
                self.assertNotIn("javascript:", text)
                self.assertNotIn("secret@", text)
                self.assertNotIn("x" * 2100, text)

    def test_cancellation_through_rpc_keeps_parent_process_alive(self):
        for query in ["slow", "slow-body"]:
            with self.subTest(query=query):
                self.check_cancellation(query)

    def check_cancellation(self, query):
        self.server.started.clear()
        self.server.body_started.clear()
        self.server.release.clear()
        args, env = self.command(query)
        process = subprocess.Popen(
            args + ["--mode", "rpc"],
            cwd=self.root,
            env=env,
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
            process.stdin.write(json.dumps({"type": "prompt", "message": "Run fixture"}) + "\n")
            process.stdin.flush()
            started = self.server.body_started if query == "slow-body" else self.server.started
            self.assertTrue(started.wait(timeout=10))
            process.stdin.write(json.dumps({"type": "abort"}) + "\n")
            process.stdin.flush()
            deadline = time.monotonic() + 10
            while True:
                event = events.get(timeout=max(0.001, deadline - time.monotonic()))
                if event["type"] == "tool_execution_end":
                    self.assertTrue(event["isError"], event)
                    self.assertIn("cancelled", json.dumps(event["result"]))
                    break
            self.assertIsNone(process.poll(), "Cancellation should not require exiting Pi")
        finally:
            self.server.release.set()
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            reader.join(timeout=1)
            process.stdout.close()
            process.stderr.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
