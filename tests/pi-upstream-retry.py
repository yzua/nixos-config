#!/usr/bin/env python3
"""Exercise upstream error retries through Pi's real loader; no network or credentials."""

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

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "home-manager/modules/ai/pi/extensions/upstream-retry.ts"
ERROR = "upstream_error: native upstream response body failed"
NORMALIZED = ERROR + " (network error)"


class UpstreamRetryTests(unittest.TestCase):
    def setUp(self):
        self.pi = require_pi()
        temporary = tempfile.TemporaryDirectory(prefix="pi-upstream-retry-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.agent = self.root / "agent"
        self.agent.mkdir()
        self.calls = self.root / "calls.jsonl"
        self.env = dict(
            isolated_environment(),
            PI_CODING_AGENT_DIR=str(self.agent),
            PI_RETRY_CASE=str(self.root / "case.json"),
            PI_RETRY_CALLS=str(self.calls),
        )

    def command(self, *, fix=True, retry=None, failures=1, error=ERROR, stop_reason="error"):
        (self.agent / "settings.json").write_text(
            json.dumps(
                {
                    "compaction": {"enabled": False},
                    "retry": retry or {"enabled": True, "maxRetries": 3, "baseDelayMs": 2},
                }
            )
        )
        (self.root / "case.json").write_text(
            json.dumps({"failures": failures, "error": error, "stopReason": stop_reason})
        )
        args = [
            self.pi,
            "--offline",
            "--no-extensions",
            "--no-context-files",
            "--no-skills",
            "--no-prompt-templates",
            "--no-session",
            "--model",
            "retry-test/offline",
            "-e",
            str(ROOT / "tests/pi-upstream-retry/provider.ts"),
        ]
        if fix:
            args += ["-e", str(EXTENSION)]
        return args

    def run_fixture(self, **kwargs):
        self.calls.unlink(missing_ok=True)
        result = subprocess.run(
            self.command(**kwargs) + ["--mode", "json", "--print", "Run the offline retry fixture"],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Failed to load extension", result.stderr)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        self.assertFalse(any(event.get("type") == "extension_error" for event in events), events)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        messages = [
            event["message"]
            for event in events
            if event.get("type") == "message_end" and event["message"]["role"] == "assistant"
        ]
        return events, calls, messages

    def test_without_fix_reproduces_the_unrecognized_failure(self):
        events, calls, messages = self.run_fixture(fix=False)
        self.assertEqual(len(calls), 1)
        self.assertEqual(messages[-1]["stopReason"], "error")
        self.assertEqual(messages[-1]["errorMessage"], ERROR)
        self.assertFalse(any(event["type"] == "auto_retry_start" for event in events))

    def test_exact_failure_retries_and_recovers_without_keep_going(self):
        events, calls, messages = self.run_fixture()
        self.assertEqual(len(calls), 2, "The exact upstream body failure must retry")
        self.assertEqual(messages[0]["errorMessage"], NORMALIZED)
        self.assertEqual(messages[0]["content"][0]["text"], "PARTIAL_FIXTURE_OUTPUT")
        self.assertEqual(messages[0]["usage"]["totalTokens"], 2)
        self.assertEqual(messages[-1]["stopReason"], "stop")
        self.assertEqual(messages[-1]["content"][0]["text"], "RETRY_FIXTURE_DONE")
        self.assertEqual([e["success"] for e in events if e["type"] == "auto_retry_end"], [True])
        self.assertEqual(sum(message["role"] == "user" for message in calls[-1]["messages"]), 1)
        self.assertFalse(
            any(
                message["role"] == "assistant" and message.get("stopReason") == "error"
                for message in calls[-1]["messages"]
            ),
            "Pi should omit the failed attempt from the recovery request",
        )

    def test_persistent_failure_respects_retry_cap_and_exponential_backoff(self):
        events, calls, messages = self.run_fixture(failures=100)
        self.assertEqual(len(calls), 4)
        retries = [event for event in events if event["type"] == "auto_retry_start"]
        self.assertEqual([event["attempt"] for event in retries], [1, 2, 3])
        self.assertEqual([event["delayMs"] for event in retries], [2, 4, 8])
        self.assertEqual(messages[-1]["stopReason"], "error")
        self.assertEqual([e["success"] for e in events if e["type"] == "auto_retry_end"], [False])

    def test_disabled_or_zero_retries_remain_disabled(self):
        for retry in [{"enabled": False}, {"enabled": True, "maxRetries": 0}]:
            with self.subTest(retry=retry):
                events, calls, messages = self.run_fixture(retry=retry)
                self.assertEqual(len(calls), 1)
                self.assertEqual(messages[-1]["errorMessage"], NORMALIZED)
                self.assertFalse(any(e["type"] == "auto_retry_start" for e in events))

    def test_unrelated_auth_quota_and_other_upstream_errors_are_unchanged(self):
        for error in [
            "invalid_api_key: authentication failed",
            "insufficient_quota: billing required",
            "upstream_error: invalid request body",
            ERROR + "; insufficient_quota",
            NORMALIZED + "; billing required",
        ]:
            with self.subTest(error=error):
                events, calls, messages = self.run_fixture(error=error)
                self.assertEqual(len(calls), 1)
                self.assertEqual(messages[-1]["errorMessage"], error)
                self.assertFalse(any(e["type"] == "auto_retry_start" for e in events))

    def test_aborted_and_successful_messages_are_not_normalized(self):
        for reason in ["aborted", "stop"]:
            with self.subTest(reason=reason):
                events, calls, messages = self.run_fixture(stop_reason=reason)
                self.assertEqual(len(calls), 1)
                self.assertEqual(messages[-1]["errorMessage"], ERROR)
                self.assertFalse(any(e["type"] == "auto_retry_start" for e in events))

    def test_cancelling_backoff_stops_retries_and_keeps_pi_alive(self):
        args = self.command(
            failures=100,
            retry={"enabled": True, "maxRetries": 3, "baseDelayMs": 10_000},
        )
        process = subprocess.Popen(
            args + ["--mode", "rpc"],
            cwd=self.root,
            env=self.env,
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

        def send(command):
            process.stdin.write(json.dumps(command) + "\n")
            process.stdin.flush()

        def until(kind):
            deadline = time.monotonic() + 10
            while True:
                event = events.get(timeout=max(0.001, deadline - time.monotonic()))
                if event["type"] == kind:
                    return event

        try:
            send({"type": "prompt", "message": "Run the offline retry fixture"})
            self.assertEqual(until("auto_retry_start")["delayMs"], 10_000)
            send({"type": "abort"})
            ended = until("auto_retry_end")
            self.assertFalse(ended["success"])
            self.assertEqual(ended["finalError"], "Retry cancelled")
            self.assertTrue(until("agent_settled")["aborted"])
            self.assertEqual(len(self.calls.read_text().splitlines()), 1)
            self.assertIsNone(process.poll())
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
