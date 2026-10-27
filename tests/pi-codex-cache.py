#!/usr/bin/env python3
"""Check Codex-LB session affinity through Pi's real loader and a loopback server."""

import http.server
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_test_support import isolated_environment, require_pi

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "home-manager/modules/ai/pi-base/extensions/codex-lb-session.ts"
PROBE = ROOT / "tests/pi-codex-cache/probe.ts"


class ResponsesFixture(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(
            (self.path, {k.lower(): v for k, v in self.headers.items()}, body)
        )
        message = {
            "id": "msg_fixture",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "fixture done", "annotations": []}],
            "status": "completed",
        }
        response = {
            "id": "resp_fixture",
            "object": "response",
            "status": "completed",
            "output": [message],
            "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
        }
        events = [
            {"type": "response.created", "response": {**response, "output": []}},
            {"type": "response.output_item.added", "output_index": 0, "item": message},
            {"type": "response.output_item.done", "output_index": 0, "item": message},
            {"type": "response.completed", "response": response},
        ]
        raw = "".join("data: " + json.dumps(event) + "\n\n" for event in events).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class CodexCache(unittest.TestCase):
    def setUp(self):
        self.pi = require_pi()
        temporary = tempfile.TemporaryDirectory(prefix="pi-codex-cache-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.agent = self.root / "agent"
        self.agent.mkdir()
        (self.agent / "settings.json").write_text(
            json.dumps({"retry": {"enabled": False}, "compaction": {"enabled": False}})
        )
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ResponsesFixture)
        self.server.requests = []
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}/v1"
        providers = {}
        for name in ("codex-lb", "unrelated"):
            providers[name] = {
                "baseUrl": self.base,
                "api": "openai-responses",
                "apiKey": "PRIVATE_FIXTURE_KEY",
                "headers": {"X-Fixture-Provider": name},
                "models": [
                    {
                        "id": "fixture",
                        "name": "Fixture model",
                        "reasoning": True,
                        "input": ["text"],
                        "contextWindow": 123456,
                        "maxTokens": 100,
                    }
                ],
            }
        (self.agent / "models.json").write_text(json.dumps({"providers": providers}))
        self.env = dict(
            isolated_environment(),
            PI_CODING_AGENT_DIR=str(self.agent),
            PI_CACHE_CASE=str(self.root / "case.json"),
        )

    def run_fixture(self, *, fix=True, probe=PROBE, **case):
        (self.root / "case.json").write_text(json.dumps(case))
        args = [
            self.pi,
            "--offline",
            "--no-extensions",
            "--no-context-files",
            "--no-skills",
            "--no-prompt-templates",
            "--no-session",
            "--model",
            "unrelated/fixture",
            "-e",
            str(probe),
        ]
        if fix:
            args += ["-e", str(EXTENSION)]
        result = subprocess.run(
            args + ["--mode", "json", "--print", "Run the local cache fixture"],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Failed to load extension", result.stderr)
        self.assertNotIn("Extension error", result.stderr)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        self.assertFalse(any(e.get("type") == "extension_error" for e in events), events)
        self.assertTrue(self.server.requests, result.stdout + result.stderr)
        return [r for r in self.server.requests if r[1].get("x-fixture-probe") == "1"]

    def test_restricted_child_launch_and_resume_keep_transport_affinity(self):
        plan_file = self.root / "child-plans.json"
        subagents = (
            ROOT
            / "home-manager/modules/ai/pi-base/extensions/interactive-subagents/pi-extension/subagents"
        )
        self.run_fixture(
            fix=False,
            probe=ROOT / "tests/pi-codex-cache/child-launch.ts",
            subagentsDir=str(subagents),
            planFile=str(plan_file),
        )
        plans = json.loads(plan_file.read_text())
        for plan in plans:
            self.assertIn("--no-extensions", plan["parts"])
            self.assertEqual(plan["loadout"]["toolAllowlist"], "read,ask_question")
            self.server.requests.clear()
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    " ".join(plan["parts"])
                    + " --offline --no-context-files --no-skills --no-prompt-templates --mode json --print",
                ],
                cwd=self.root,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("Extension error", result.stderr)
            self.assertEqual(len(self.server.requests), 1, result.stderr)
            _, headers, body = self.server.requests[0]
            self.assertEqual(headers.get("session-id"), body["prompt_cache_key"])
            self.assertEqual(headers["session_id"], body["prompt_cache_key"])
            self.assertEqual(
                {tool["name"] for tool in body["tools"]},
                {"read", "ask_question"},
                "Transport support must not widen a restricted child's tools",
            )

    def test_without_fix_reproduces_underscore_only_header(self):
        _, headers, body = self.run_fixture(fix=False)[0]
        self.assertEqual(headers["session_id"], body["prompt_cache_key"])
        self.assertNotIn("session-id", headers)

    def test_copies_each_actual_request_identity_without_changing_auth_or_payload(self):
        requests = self.run_fixture(sessionIds=["first-session", "second-session"])
        self.assertEqual(len(requests), 2)
        for (path, headers, body), sid in zip(requests, ["first-session", "second-session"]):
            self.assertEqual(path, "/v1/responses")
            self.assertEqual(headers["session-id"], sid)
            self.assertEqual(headers["session_id"], sid)
            self.assertEqual(body["prompt_cache_key"], sid)
            self.assertEqual(headers["authorization"], "Bearer PRIVATE_FIXTURE_KEY")
            self.assertEqual(headers["x-fixture-provider"], "codex-lb")
            self.assertEqual(body["model"], "fixture")
            self.assertEqual(body["reasoning"]["effort"], "low")
            self.assertEqual(body["input"][-1]["content"][0]["text"], "Synthetic fixture")

    def test_explicit_underscore_identity_or_opt_out_controls_the_alias(self):
        for value in ("caller-session", None):
            with self.subTest(value=value):
                self.server.requests.clear()
                _, headers, _ = self.run_fixture(headers={"session_id": value})[0]
                if value is None:
                    self.assertNotIn("session-id", headers)
                    self.assertNotIn("session_id", headers)
                else:
                    self.assertEqual(headers["session-id"], value)
                    self.assertEqual(headers["session_id"], value)

    def test_unrelated_provider_is_unchanged(self):
        _, headers, body = self.run_fixture(provider="unrelated")[0]
        self.assertEqual(headers["session_id"], body["prompt_cache_key"])
        self.assertNotIn("session-id", headers)

    def test_explicit_alias_or_null_opt_out_is_preserved_case_insensitively(self):
        for value in ("explicit-session", None):
            with self.subTest(value=value):
                self.server.requests.clear()
                _, headers, _ = self.run_fixture(headers={"SeSsIoN-Id": value})[0]
                if value is None:
                    self.assertNotIn("session-id", headers)
                else:
                    self.assertEqual(headers["session-id"], value)

    def test_no_session_or_disabled_caching_does_not_invent_affinity(self):
        for case in ({"sessionIds": [None]}, {"cacheRetention": "none"}):
            with self.subTest(case=case):
                self.server.requests.clear()
                _, headers, body = self.run_fixture(**case)[0]
                self.assertNotIn("session-id", headers)
                self.assertNotIn("prompt_cache_key", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
