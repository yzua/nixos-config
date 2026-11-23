#!/usr/bin/env python3
"""Check Codex-LB session affinity through Pi's real loader and a loopback server."""

import base64
import hashlib
import http.server
import json
import struct
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
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def events(self, *, tools=False):
        message = {
            "id": "msg_fixture",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "fixture done", "annotations": []}],
            "status": "completed",
        }
        output = [message]
        if tools:
            output = [
                {"id": "rs_fixture", "type": "reasoning", "summary": [],
                 "encrypted_content": "fixture-encrypted-reasoning"},
                {"id": "fc_fixture", "type": "function_call", "call_id": "call_fixture",
                 "name": "fixture_tool", "arguments": '{"value":1}', "status": "completed"},
            ]
        response = {
            "id": "resp_fixture",
            "object": "response",
            "status": "completed",
            "output": output,
            "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
        }
        events = [{"type": "response.created", "response": {**response, "output": []}}]
        for index, item in enumerate(output):
            events += [
                {"type": "response.output_item.added", "output_index": index, "item": item},
                {"type": "response.output_item.done", "output_index": index, "item": item},
            ]
        return events + [{"type": "response.completed", "response": response}]

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(
            (self.path, {k.lower(): v for k, v in self.headers.items()}, body)
        )
        raw = "".join("data: " + json.dumps(event) + "\n\n" for event in self.events()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_frame(self, text):
        raw = text.encode()
        length = len(raw)
        prefix = bytes([0x81, length]) if length < 126 else b"\x81\x7e" + struct.pack("!H", length)
        self.wfile.write(prefix + raw)

    def read_frame(self):
        frame = self.rfile.read(2)
        if len(frame) != 2:
            return None
        length = frame[1] & 127
        if length == 126:
            length = struct.unpack("!H", self.rfile.read(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self.rfile.read(8))[0]
        if length > 1048576:
            raise ValueError("Oversized synthetic fixture")
        mask = self.rfile.read(4) if frame[1] & 128 else b"\0" * 4
        raw = self.rfile.read(length)
        return json.loads(bytes(value ^ mask[i % 4] for i, value in enumerate(raw)))

    def do_GET(self):
        # These local-only barriers let the probe verify cleanup before its
        # process exits; they never forward a provider request or credentials.
        if self.path.endswith("/fixture-closed") or self.path.endswith("/fixture-ready"):
            closed = self.path.endswith("/fixture-closed")
            ready = (self.server.closed if closed else self.server.started).wait(1)
            raw = json.dumps({"ready": ready, "close_frame": self.server.closed_frame}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        headers = {k.lower(): v for k, v in self.headers.items()}
        self.server.started.set()
        if self.server.mode == "handshake-stall":
            self.server.requests.append((self.path, headers, {}))
            self.connection.settimeout(3)
            self.rfile.read(1)
            self.server.closed.set()
            self.close_connection = True
            return
        if self.server.mode in ("reject", "redirect"):
            self.server.requests.append((self.path, headers, {}))
            self.send_response(503 if self.server.mode == "reject" else 302)
            self.send_header("Location", getattr(self.server, "redirect", self.server.base + "/redirect-target"))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        accept = base64.b64encode(hashlib.sha1(
            (self.headers["Sec-WebSocket-Key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
        ).digest()).decode()
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        if self.server.mode == "tools":
            self.connection.settimeout(3)
            for turn in range(2):
                body = self.read_frame()
                self.server.requests.append((self.path, headers, body))
                for event in self.events(tools=turn == 0):
                    self.send_frame(json.dumps(event))
            self.wfile.write(b"\x88\x00")
            self.close_connection = True
            return
        body = self.read_frame()
        if body is None:
            return
        self.server.requests.append((self.path, headers, body))
        if self.server.mode == "malformed":
            self.send_frame("not JSON")
        elif self.server.mode == "policy":
            self.send_frame(json.dumps({"type": "error", "error": {
                "code": "cyber_policy", "message": "Synthetic policy refusal"
            }}))
        elif self.server.mode == "hook-stall":
            self.send_frame(json.dumps(self.events()[0]))
        elif self.server.mode not in ("close", "stall"):
            for event in self.events():
                self.send_frame(json.dumps(event))
        if self.server.mode in ("stall", "hook-stall"):
            self.connection.settimeout(3)
            frame = self.rfile.read(2)
            self.server.closed_frame = len(frame) == 2 and frame[0] & 15 == 8
            self.server.closed.set()
        else:
            self.wfile.write(b"\x88\x00")
        self.close_connection = True


class ResponsesTests(unittest.TestCase):
    provider = "codex-lb"

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
        self.server.mode = "normal"
        self.server.closed = threading.Event()
        self.server.started = threading.Event()
        self.server.closed_frame = False
        self.addCleanup(self.server.server_close)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}/v1"
        self.server.base = self.base
        providers = {}
        for name in ("codex-lb", "codex-daybreak", "unrelated"):
            providers[name] = {
                "baseUrl": self.base,
                "api": "openai-responses",
                "apiKey": f"PRIVATE_FIXTURE_KEY_{name}",
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
        claims = {"https://api.openai.com/auth": {"chatgpt_account_id": "fixture-direct-account"}}
        encoded = base64.b64encode(json.dumps(claims).encode()).decode()
        self.direct_token = f"fixture.{encoded}.signature"
        providers["codex-cyber-daybreak"] = {
            "baseUrl": self.base,
            "api": "openai-codex-responses",
            "models": providers["codex-lb"]["models"],
        }
        (self.agent / "auth.json").write_text(json.dumps({"codex-cyber-daybreak": {
            "type": "oauth", "access": self.direct_token, "refresh": "fixture-refresh",
            "expires": 4102444800000, "accountId": "fixture-direct-account",
        }}))
        (self.agent / "models.json").write_text(json.dumps({"providers": providers}))
        self.env = dict(
            isolated_environment(),
            PI_CODING_AGENT_DIR=str(self.agent),
            PI_CACHE_CASE=str(self.root / "case.json"),
        )

    def run_fixture(self, *, fix=True, probe=PROBE, **case):
        case.setdefault("provider", self.provider)
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


class CodexCache(ResponsesTests):
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
            model=f"{self.provider}/fixture",
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
            if self.provider == "codex-daybreak":
                self.assertEqual(headers.get("upgrade"), "websocket")
                self.assertEqual(headers.get("x-codex-lb-required-capability"), "trusted_cyber")
                self.assertEqual(body.get("access_programs"), {"cyber": "daybreak_blue"})
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
            self.assertEqual(headers["authorization"], f"Bearer PRIVATE_FIXTURE_KEY_{self.provider}")
            self.assertEqual(headers["x-fixture-provider"], self.provider)
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


class DaybreakCache(CodexCache):
    provider = "codex-daybreak"

    def test_requires_websocket_program_and_capability(self):
        _, headers, body = self.run_fixture()[0]
        self.assertEqual(headers.get("upgrade"), "websocket")
        self.assertEqual(headers.get("x-codex-lb-required-capability"), "trusted_cyber")
        self.assertEqual(body.get("type"), "response.create")
        self.assertEqual(body.get("access_programs"), {"cyber": "daybreak_blue"})

    def test_hooks_cannot_weaken_required_access(self):
        _, headers, body = self.run_fixture(
            headers={"x-codex-lb-required-capability": None},
            payload={"access_programs": {"cyber": "ordinary"}, "type": "other", "store": True},
        )[0]
        self.assertEqual(headers["x-codex-lb-required-capability"], "trusted_cyber")
        self.assertEqual(body["access_programs"]["cyber"], "daybreak_blue")
        self.assertEqual(body["type"], "response.create")
        self.assertFalse(body["store"])

    def test_handshake_denial_never_falls_back_to_http_or_retries(self):
        self.server.mode = "reject"
        requests = self.run_fixture(expectedError="WebSocket handshake failed")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][1]["upgrade"], "websocket")

    def test_redirect_does_not_reach_another_listener(self):
        destination = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ResponsesFixture)
        destination.requests = []
        destination.started = threading.Event()
        destination.mode = "reject"
        destination.base = f"http://127.0.0.1:{destination.server_port}"
        self.addCleanup(destination.server_close)
        threading.Thread(target=destination.serve_forever, daemon=True).start()
        self.addCleanup(destination.shutdown)
        self.server.mode = "redirect"
        self.server.redirect = destination.base + "/redirect-target"
        requests = self.run_fixture(expectedError="WebSocket handshake failed")
        self.assertEqual(len(requests), 1)
        self.assertEqual(destination.requests, [], "Redirect must never forward credentials")

    def test_interrupted_submission_is_not_replayed(self):
        self.server.mode = "close"
        requests = self.run_fixture(expectedError="delivery unknown, not replayed")
        self.assertEqual(len(requests), 1)

    def test_invalid_stream_is_not_replayed(self):
        self.server.mode = "malformed"
        requests = self.run_fixture(expectedError="invalid WebSocket event")
        self.assertEqual(len(requests), 1)

    def test_upstream_policy_refusal_is_preserved(self):
        self.server.mode = "policy"
        requests = self.run_fixture(expectedError="Synthetic policy refusal")
        self.assertEqual(len(requests), 1)

    def test_abort_and_idle_deadline_close_the_socket(self):
        for case in ({"abortMs": 100, "expectedAbort": True},
                     {"timeoutMs": 100, "expectedError": "idle deadline exceeded"}):
            with self.subTest(case=case):
                self.server.mode = "stall"
                self.server.requests.clear()
                self.server.closed.clear()
                requests = self.run_fixture(expectCloseFrame=True, **case)
                self.assertEqual(len(requests), 1)
                self.assertTrue(self.server.closed_frame, "Abandoned socket")

    def test_handshake_abort_and_deadline_close_the_socket(self):
        for case in ({"abortOnHandshake": True, "expectedAbort": True},
                     {"connectTimeoutMs": 100, "expectedError": "handshake deadline exceeded"}):
            with self.subTest(case=case):
                self.server.mode = "handshake-stall"
                self.server.requests.clear()
                self.server.closed.clear()
                self.server.started.clear()
                self.run_fixture(expectClose=True, **case)
                self.assertTrue(self.server.closed.is_set(), "Handshake socket abandoned")

    def test_proxy_configuration_and_invalid_payload_fail_before_sending(self):
        for case in ({"env": {"HTTPS_PROXY": "http://127.0.0.1:1"},
                      "expectedError": "configured proxies are not supported"},
                     {"payload": [], "replacePayload": True, "expectedError": "invalid Responses payload"}):
            with self.subTest(case=case):
                self.server.requests.clear()
                self.assertEqual(self.run_fixture(**case), [])

    def test_agent_retry_policy_does_not_replay_transport_failures(self):
        (self.agent / "settings.json").write_text(json.dumps({
            "retry": {"enabled": True, "maxRetries": 2, "baseDelayMs": 1},
            "compaction": {"enabled": False},
        }))
        for mode in ("reject", "close"):
            with self.subTest(mode=mode):
                self.server.mode = mode
                self.server.requests.clear()
                result = subprocess.run([
                    self.pi, "--offline", "--no-extensions", "-e", str(EXTENSION),
                    "--no-context-files", "--no-skills", "--no-prompt-templates",
                    "--no-session", "--no-tools", "--model", "codex-daybreak/fixture",
                    "--mode", "json", "--print", "Synthetic retry fixture",
                ], cwd=self.root, env=self.env, capture_output=True, text=True, timeout=10)
                events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
                errors = [event["message"] for event in events if event.get("type") == "message_end"
                          and event.get("message", {}).get("stopReason") == "error"]
                self.assertEqual(len(errors), 1, result.stdout + result.stderr)
                self.assertIn("Codex Daybreak:", errors[0]["errorMessage"])
                self.assertEqual(len(self.server.requests), 1, "Agent silently replayed the request")
                self.assertEqual(self.server.requests[0][1]["upgrade"], "websocket")

    def test_failed_response_or_event_hooks_close_the_socket(self):
        for case in ({"responseHookError": True, "expectedError": "Fixture response hook failed"},
                     {"eventHookError": True, "expectedError": "Fixture event hook failed"}):
            with self.subTest(case=case):
                self.server.mode = "hook-stall"
                self.server.requests.clear()
                self.server.closed.clear()
                self.run_fixture(timeoutMs=2000, expectCloseFrame=True, **case)
                self.assertTrue(self.server.closed_frame, "Hook failure abandoned socket")


class DirectCodexCache(ResponsesTests):
    provider = "codex-cyber-daybreak"

    def run_fixture(self, **case):
        # Native Codex owns cached sockets by session ID. Use the real root ID
        # so Pi's session cleanup also closes nested fixture connections.
        case.setdefault("sessionIds", ["@current"])
        return super().run_fixture(**case)

    def test_native_oauth_uses_direct_model_endpoint_without_lb_auth(self):
        path, headers, body = self.run_fixture()[0]
        self.assertEqual(path, "/v1/codex/responses")
        self.assertEqual(headers.get("upgrade"), "websocket")
        self.assertEqual(headers["authorization"], f"Bearer {self.direct_token}")
        self.assertEqual(headers["chatgpt-account-id"], "fixture-direct-account")
        self.assertNotIn("x-codex-lb-required-capability", headers)
        self.assertEqual(body["access_programs"], {"cyber": "daybreak_blue"})
        self.assertFalse(body["store"])

    def test_payload_hook_cannot_remove_the_daybreak_selection(self):
        _, _, body = self.run_fixture(payload={"access_programs": {"cyber": "standard"}, "store": True})[0]
        self.assertEqual(body["access_programs"], {"cyber": "daybreak_blue"})
        self.assertFalse(body["store"])

    def test_reasoning_tool_roundtrip_and_raw_stream_keep_full_daybreak_context(self):
        self.server.mode = "tools"
        requests = self.run_fixture(probe=ROOT / "tests/pi-codex-cache/direct.ts")
        self.assertEqual(len(requests), 2)
        for _, headers, body in requests:
            self.assertEqual(headers["authorization"], f"Bearer {self.direct_token}")
            self.assertEqual(body["access_programs"], {"cyber": "daybreak_blue"})
            self.assertNotIn("previous_response_id", body)
        second = requests[1][2]
        calls = [item for item in second["input"] if item.get("type") == "function_call"]
        results = [item for item in second["input"] if item.get("type") == "function_call_output"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(calls[0]["call_id"], results[0]["call_id"])
        self.assertTrue(any(item.get("encrypted_content") == "fixture-encrypted-reasoning"
                            for item in second["input"] if item.get("type") == "reasoning"))

    def test_hook_injected_continuation_fails_before_sending(self):
        self.assertEqual(self.run_fixture(
            payload={"previous_response_id": "resp_foreign"},
            expectedError="previous_response_id is unsupported",
        ), [])

    def test_direct_policy_refusal_is_not_hidden_or_rerouted(self):
        self.server.mode = "policy"
        requests = self.run_fixture(expectedError="Synthetic policy refusal")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][1]["authorization"], f"Bearer {self.direct_token}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
