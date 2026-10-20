#!/usr/bin/env python3
"""Offline named research-worker ownership and real-Pi read-only/resume fixtures."""

import http.server
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from pi_test_support import isolated_environment, require_pi, require_web_fetch_dependencies

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "home-manager/modules/ai/pi-re"
sys.path.insert(0, str(CODE))
spec = importlib.util.spec_from_file_location("pi_re_research", CODE / "research.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)

FAKE_PI = r"""
import json, os, signal, sys, time
from pathlib import Path
args = sys.argv[1:]
sessions = Path(args[args.index("--session-dir") + 1])
resume = "--session" in args
if resume:
    native = Path(args[args.index("--session") + 1])
else:
    session_id = args[args.index("--session-id") + 1]
    native = sessions / ("fixture_" + session_id + ".jsonl")
    native.write_text(json.dumps({"type":"session", "id": session_id}) + "\n")
with native.open("a") as stream:
    stream.write(json.dumps({"type":"fixture", "args":args, "cwd":os.getcwd(),
        "env":{k:v for k,v in os.environ.items() if k.startswith(("PI_", "HERDR_", "TMUX"))}})+"\n")
if os.environ.get("TEST_MODE") == "sleep":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(60)
message = {"role":"assistant", "provider":"zai", "model":"glm-5.3-flash",
    "content":[{"type":"text","text":"resume-new-output" if resume else "first-output"}],
    "stopReason":"stop", "usage":{"input":2,"output":3}}
print(json.dumps({"type":"message_end","message":message}), flush=True)
"""


class Research(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pi-re-research-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = isolated_environment()
        for key in list(self.env):
            if key.startswith(("PI_", "XDG_")):
                del self.env[key]
        self.env.update(
            HOME=str(self.root / "home"),
            XDG_DATA_HOME=str(self.root / "data"),
            XDG_STATE_HOME=str(self.root / "state"),
        )
        self.agent, self.state = helper.caller_paths(self.env)
        helper.private_directory(self.agent)
        helper.private_directory(self.state)
        helper.private_directory(self.state / "sessions")
        self.parent = self.state / "sessions/root.jsonl"
        self.parent.write_text('{"type":"session","id":"root"}\n')
        self.parent.chmod(0o600)
        self.cwd = self.root / "sources"
        self.cwd.mkdir()
        (self.cwd / "notes.txt").write_text("SOURCE_REVIEW_MARKER\n")
        (self.cwd / ".env").write_text("PRIVATE_SOURCE_KEY_CANARY")
        self.fake = self.root / "pi"
        self.fake.write_text(f"#!{sys.executable}\n" + FAKE_PI)
        self.fake.chmod(0o700)
        self.config = self.root / "runtime.json"
        self.value = {
            "pi": str(self.fake),
            "python": sys.executable,
            "resources": str(CODE),
            "webSearchExtension": str(
                ROOT / "home-manager/modules/ai/pi-base/extensions/web-search/index.ts"
            ),
            "webFetchExtension": str(
                ROOT / "home-manager/modules/ai/pi-base/extensions/web-fetch/index.ts"
            ),
            "research": {"maxConcurrent": 4, "defaultTimeoutSeconds": 10, "maxTimeoutSeconds": 30},
        }
        self.config.write_text(json.dumps(self.value))
        self.env.update(
            PI_PROFILE="pi-re", PI_CODING_AGENT_DIR=str(self.agent), PI_RE_CONFIG=str(self.config)
        )
        self.children = []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for child in self.children:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream:
                    stream.close()

    def run_worker(self, name="manual", task="Review owned sources", **kwargs):
        return helper.run_turn(
            self.config, self.state, self.parent, name, task, cwd=self.cwd, env=self.env, **kwargs
        )

    def cli(self, name, *, mode="sleep", resume=False, timeout=20):
        args = [
            sys.executable,
            "-B",
            str(CODE / "research.py"),
            "--config",
            str(self.config),
            "--state-dir",
            str(self.state),
            "--parent",
            str(self.parent),
            "--name",
            name,
            "--timeout",
            str(timeout),
        ]
        args.extend(["--resume"] if resume else ["--cwd", str(self.cwd)])
        proc = subprocess.Popen(
            args,
            env=dict(self.env, TEST_MODE=mode),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc.stdin.write(b"Review the owned source fixture")
        proc.stdin.close()
        self.children.append(proc)
        return proc

    def metadata(self, name):
        return (
            self.state
            / "research"
            / helper.parent_key(self.state, self.parent)
            / name
            / "metadata.json"
        )

    def ready(self, name):
        end = time.monotonic() + 5
        while time.monotonic() < end:
            path = self.metadata(name)
            if path.exists():
                value = json.loads(path.read_text())
                if value.get("phase") == "running":
                    return value
            time.sleep(0.01)
        self.fail("Research worker did not start")

    def test_named_resume_keeps_session_cwd_loadout_and_returns_new_output(self):
        first = self.run_worker()
        native = Path(json.loads(self.metadata("manual").read_text())["session"])
        second = self.run_worker(task="Follow up", resume=True)
        self.assertEqual(first["result"], "first-output")
        self.assertEqual(second["result"], "resume-new-output")
        self.assertEqual(second["turn"], 2)
        self.assertTrue(second["resumable"])
        calls = [json.loads(line) for line in native.read_text().splitlines()][1:]
        self.assertIn("--session-id", calls[0]["args"])
        self.assertIn("--session", calls[1]["args"])
        self.assertIn(str(native), calls[1]["args"])
        for call in calls:
            self.assertEqual(call["cwd"], str(self.cwd))
            self.assertEqual(call["env"]["PI_RE_RESEARCH_ROOT"], str(self.cwd))
            self.assertIn("--no-builtin-tools", call["args"])
            self.assertIn("--no-mcp", call["args"])
            self.assertIn("research_read,research_list,web_search,web_fetch", call["args"])
            self.assertNotIn("contract.md", " ".join(call["args"]))
            self.assertFalse(
                any(key.startswith(("HERDR_", "TMUX", "PI_SUBAGENT")) for key in call["env"])
            )
        self.assertEqual(native.stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_worker()

    def test_legacy_root_permissions_and_dead_first_turn_native_recovery(self):
        self.parent.chmod(0o644)  # Native roots before the launcher's private umask.
        self.assertEqual(self.run_worker("legacy")["status"], "ok")
        self.assertEqual(self.parent.stat().st_mode & 0o777, 0o644)
        child = self.cli("crashed")
        value = self.ready("crashed")
        sessions = self.metadata("crashed").parent / "sessions"
        end = time.monotonic() + 3
        while not list(sessions.glob("*.jsonl")) and time.monotonic() < end:
            time.sleep(0.01)
        self.assertTrue(list(sessions.glob("*.jsonl")))
        child.kill()
        child.wait(timeout=3)
        end = time.monotonic() + 3
        while (
            helper.process_identity(value["writer"]["pid"]) is not None and time.monotonic() < end
        ):
            time.sleep(0.01)
        self.assertIsNone(helper.process_identity(value["writer"]["pid"]))
        self.assertNotIn("session", json.loads(self.metadata("crashed").read_text()))
        self.assertEqual(self.run_worker("crashed", resume=True)["result"], "resume-new-output")

    def test_four_concurrent_workers_reject_fifth_and_same_name_resume(self):
        for name in ("one", "two", "three", "four"):
            self.cli(name)
            self.ready(name)
        fifth = self.cli("five", mode="ok")
        fifth.wait(timeout=3)
        self.assertIn("At most 4", fifth.stdout.read().decode())
        self.assertFalse(self.metadata("five").parent.exists())
        same = self.cli("one", resume=True)
        same.wait(timeout=3)
        self.assertIn("already running", same.stdout.read().decode())
        self.cleanup()
        self.assertEqual(self.run_worker("five")["status"], "ok")

    def test_deadline_cancel_and_resume_preserve_ownership(self):
        child = self.cli("timeout", timeout=1)
        writer = self.ready("timeout")["writer"]
        child.wait(timeout=4)
        summary = json.loads(child.stdout.read())
        self.assertEqual(summary["status"], "timeout")
        self.assertIsNone(helper.process_identity(writer["pid"]))
        self.assertEqual(self.run_worker("timeout", resume=True)["result"], "resume-new-output")
        child = self.cli("cancel")
        writer = self.ready("cancel")["writer"]
        child.terminate()
        child.wait(timeout=4)
        self.assertEqual(json.loads(child.stdout.read())["status"], "cancelled")
        self.assertIsNone(helper.process_identity(writer["pid"]))

    def test_resume_rejects_foreign_parent_changed_loadout_and_bad_native_identity(self):
        self.run_worker()
        other = self.parent.with_name("other.jsonl")
        other.write_text("fixture")
        other.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            helper.run_turn(
                self.config, self.state, other, "manual", "Follow up", resume=True, env=self.env
            )
        value = json.loads(self.metadata("manual").read_text())
        native = Path(value["session"])
        original = native.read_bytes()
        native.write_text('{"type":"session","id":"foreign"}\n')
        with self.assertRaisesRegex(ValueError, "identity"):
            self.run_worker(resume=True)
        native.write_bytes(original)
        self.config.write_text(json.dumps({**self.value, "extra": "changed"}))
        with self.assertRaisesRegex(ValueError, "loadout"):
            self.run_worker(resume=True)

    def test_rejects_unknown_writer_symlink_metadata_and_unbounded_policy(self):
        self.run_worker()
        metadata = self.metadata("manual")
        value = json.loads(metadata.read_text())
        value.update(phase="starting", writer=None)
        helper.write_private(metadata, value)
        with self.assertRaisesRegex(ValueError, "ownership"):
            self.run_worker(resume=True)
        metadata.unlink()
        metadata.symlink_to(self.config)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.run_worker(resume=True)
        for invalid in (
            {"maxConcurrent": 5},
            {"defaultTimeoutSeconds": 0},
            {"maxTimeoutSeconds": 4000},
            {"maxConcurrent": True},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                helper.policy({"research": invalid})
        with self.assertRaises(ValueError):
            self.run_worker("bad/name")
        with self.assertRaises(ValueError):
            self.run_worker("too-long", timeout=31)

    def configure_native(self):
        self.value["pi"] = require_pi()
        self.value["webFetchExtension"] = str(
            require_web_fetch_dependencies().resolve() / "index.ts"
        )
        self.config.write_text(json.dumps(self.value))
        self.requests = []
        self.requested_tool = ("research_read", {"path": "notes.txt"})
        testcase = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                testcase.requests.append(body)
                names = {tool["function"]["name"] for tool in body.get("tools", [])}
                testcase.assertEqual(
                    names, {"research_read", "research_list", "web_search", "web_fetch"}
                )
                followup = "FOLLOWUP_MARKER" in json.dumps(body)
                tool_messages = [
                    message for message in body["messages"] if message["role"] == "tool"
                ]
                if not tool_messages and not followup:
                    name, params = testcase.requested_tool
                    delta = {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "research_read_fixture",
                                "type": "function",
                                "function": {"name": name, "arguments": json.dumps(params)},
                            }
                        ],
                    }
                    finish = "tool_calls"
                else:
                    delta = {
                        "role": "assistant",
                        "content": "FOLLOWUP_RESULT" if followup else "FIRST_RESULT",
                    }
                    finish = "stop"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for piece, reason in ((delta, None), ({}, finish)):
                    chunk = {
                        "id": "fixture",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": "glm-5.3-flash",
                        "choices": [{"index": 0, "delta": piece, "finish_reason": reason}],
                    }
                    self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        model = {
            "id": "glm-5.3-flash",
            "name": "Fixture",
            "reasoning": False,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 128000,
            "maxTokens": 1024,
        }
        helper.write_private(
            self.agent / "models.json",
            {
                "providers": {
                    "zai": {
                        "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                        "api": "openai-completions",
                        "apiKey": "RESEARCH_AUTH_CANARY",
                        "models": [model],
                    }
                }
            },
        )
        helper.write_private(
            self.agent / "settings.json",
            {
                "extensions": ["-builtin:mcp"],
                "enableInstallTelemetry": False,
                "enableAnalytics": False,
            },
        )
        helper.write_private(self.agent / "auth.json", {})

    def test_real_pi_read_only_tools_and_native_followup_history(self):
        self.configure_native()
        first = self.run_worker(task="FIRST_TASK_MARKER: review source notes")
        self.assertEqual(first["status"], "ok", first)
        self.assertEqual(first["result"], "FIRST_RESULT")
        self.assertIn("SOURCE_REVIEW_MARKER", json.dumps(self.requests))
        self.requests.clear()
        second = self.run_worker(task="FOLLOWUP_MARKER: summarize prior source", resume=True)
        self.assertEqual(second["status"], "ok", second)
        self.assertEqual(second["result"], "FOLLOWUP_RESULT")
        history = json.dumps(self.requests)
        self.assertIn("FIRST_TASK_MARKER", history)
        self.assertIn("FIRST_RESULT", history)
        self.assertNotIn("RESEARCH_AUTH_CANARY", history)
        self.assertNotIn("PRIVATE_SOURCE_KEY_CANARY", history)

    def test_real_pi_blocks_shell_private_paths_and_outside_symlinks(self):
        self.configure_native()
        outside = self.root / "outside.txt"
        outside.write_text("OUTSIDE_SOURCE_CANARY")
        (self.cwd / "link.txt").symlink_to(outside)
        binary = self.cwd / "sample.bin"
        binary.write_bytes(b"\x00binary")
        for index, tool in enumerate(
            (
                ("bash", {"command": "touch escaped"}),
                ("research_read", {"path": ".env"}),
                ("research_read", {"path": "../outside.txt"}),
                ("research_read", {"path": "link.txt"}),
                ("research_read", {"path": "sample.bin"}),
            )
        ):
            with self.subTest(tool=tool):
                self.requests.clear()
                self.requested_tool = tool
                summary = self.run_worker(f"blocked-{index}")
                self.assertEqual(summary["status"], "ok", summary)
                content = json.dumps(self.requests)
                self.assertNotIn("PRIVATE_SOURCE_KEY_CANARY", content)
                self.assertNotIn("OUTSIDE_SOURCE_CANARY", content)
                results = [
                    message
                    for request in self.requests
                    for message in request["messages"]
                    if message["role"] == "tool"
                ]
                self.assertTrue(results, content)
                self.assertFalse((self.cwd / "escaped").exists())


if __name__ == "__main__":
    unittest.main()
