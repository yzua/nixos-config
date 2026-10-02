#!/usr/bin/env python3
"""Offline pi-re Flash ownership tests; never invoke a provider, device or real Pi."""

import importlib.util
import io
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "home-manager/modules/ai/pi-re/subagent.py"
spec = importlib.util.spec_from_file_location("re_subagent", HELPER)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)

FAKE_LAUNCHER = r"""
import json, os, signal, subprocess, sys, time
from pathlib import Path
sessions = Path(os.environ["PI_RE_CHILD_SESSION_DIR"])
# A fake native session and invocation record prove our selected caller path and flags.
(sessions / "native.jsonl").write_text(json.dumps({"type": "session", "id": sessions.parent.name}) + "\n")
os.chmod(sessions / "native.jsonl", 0o600)
(sessions / "invocation.json").write_text(json.dumps({"args": sys.argv[1:], "cwd": os.getcwd(),
    "pid": os.getpid(), "env": {k: v for k, v in os.environ.items() if k.startswith("PI_") or k.startswith("TEST_")}}))
os.chmod(sessions / "invocation.json", 0o600)
mode = os.environ.get("TEST_MODE", "ok")
def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)
def msg(text, reason="stop", **kw):
    return {"role": "assistant", "provider": "zai", "model": "glm-5.3-flash", "content": [
        {"type": "thinking", "thinking": "private thinking not forwarded"},
        {"type": "text", "text": text}, {"type": "toolCall", "name": "not text", "arguments": {}}],
        "stopReason": reason, "usage": {"input": 2, "output": 3, "cost": {"total": 0.01}}, **kw}
if mode == "unsafe-session-symlink":
    (sessions / "foreign.jsonl").symlink_to(os.environ["TEST_UNSAFE_TARGET"])
elif mode == "unsafe-session-hardlink":
    os.link(os.environ["TEST_UNSAFE_TARGET"], sessions / "foreign.jsonl")
if mode in ("sleep", "descendant"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if mode == "descendant":
        child = subprocess.Popen([sys.executable, "-c", "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)"])
        (sessions / "descendant.pid").write_text(str(child.pid))
    time.sleep(60)
elif mode == "error":
    emit({"type": "message_end", "message": msg("failed", "error", errorMessage="fixture provider failure")})
elif mode == "aborted":
    emit({"type": "message_end", "message": msg("stopped", "aborted")})
elif mode == "wrong-model":
    emit({"type": "message_end", "message": msg("wrong", model="other-model")})
elif mode == "nonzero":
    emit({"type": "message_end", "message": msg("response")})
    sys.exit(7)
elif mode == "agent-end":
    emit({"type": "agent_end", "messages": [msg("fallback")], "willRetry": False})
elif mode == "malformed":
    print("not-json", flush=True)
    emit({"type": "message_end", "message": msg("still useful")})
elif mode == "oversized-line":
    print("x" * 400000, flush=True)
    emit({"type": "message_end", "message": msg("recovered")})
elif mode == "huge":
    for _ in range(50):
        emit({"type": "ignored", "data": "x" * 50000})
    sys.stderr.write("private diagnostics" * 20000)
    emit({"type": "message_end", "message": msg('漢字\\\"\n' * 10000)})
elif mode == "delta":
    emit({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "preview"}})
elif mode == "retry":
    emit({"type": "agent_start"})
    emit({"type": "message_end", "message": msg("first failure", "error", errorMessage="earlier error")})
    emit({"type": "agent_end", "messages": [msg("first failure", "error")]})
    emit({"type": "agent_start"})
    emit({"type": "message_end", "message": msg("retry success")})
    emit({"type": "agent_end", "messages": [msg("retry success")]})
else:
    emit({"type": "session", "id": "ignored", "parentSession": "/foreign/session.jsonl"})
    emit({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "not authoritative"}})
    emit({"type": "message_end", "message": {"role": "toolResult", "content": [{"type": "text", "text": "tool private text"}]}})
    emit({"type": "tool_execution_end", "result": {"content": [{"type": "text", "text": "tool event text"}]}})
    emit({"type": "message_end", "message": msg("final\u2028line\u2029paragraph")})
    emit({"type": "agent_end", "messages": [msg("duplicate")]})
    emit({"type": "agent_settled"})
"""


class FlashTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.resources = self.root / "resources"
        self.resources.mkdir(mode=0o700)
        (self.resources / "launcher.py").write_text(FAKE_LAUNCHER)
        self.config = self.root / "config.json"
        self.config.write_text(
            json.dumps({"python": sys.executable, "resources": str(self.resources)})
        )
        self.cwd = self.root / "hostile-workspace"
        self.cwd.mkdir()
        (self.cwd / ".pi").mkdir()
        (self.cwd / ".pi/settings.json").write_text(
            '{"defaultModel":"foreign","extensions":["evil.ts"]}'
        )
        self.env = dict(
            os.environ,
            HOME=str(self.root / "home"),
            XDG_DATA_HOME=str(self.root / "data"),
            XDG_STATE_HOME=str(self.root / "state"),
        )
        self.agent, self.state = helper.caller_paths(self.env)
        self.env.update(
            PI_CODING_AGENT_DIR=str(self.agent),
            PI_RE_CONFIG=str(self.config),
            TEST_PROFILE="preserved",
            PI_PACKAGE_DIR="/reviewed/pi-package",
            PI_SESSION_FILE="/foreign/session",
            PI_SESSION_ID="foreign-id",
            PI_PROVIDER="foreign",
            PI_MODEL="foreign",
            PI_REASONING_LEVEL="max",
            PI_CODING_AGENT_SESSION_DIR="/foreign/sessions",
        )
        self.env.pop("PI_RE_CHILD", None)
        self.env.pop("PI_RE_CHILD_SESSION_DIR", None)
        self.original = {key: value for key, value in self.env.items()}
        self.processes = []

    def tearDown(self):
        for proc in self.processes:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream:
                    stream.close()
        self.temp.cleanup()

    def run_job(self, mode="ok", task="Inspect approved fixture", **kw):
        return helper.run_job(
            self.config, self.state, self.cwd, task, env=dict(self.env, TEST_MODE=mode), **kw
        )

    def cli(self, mode="ok", extra=()):
        proc = subprocess.Popen(
            [
                sys.executable,
                str(HELPER),
                "--config",
                str(self.config),
                "--state-dir",
                str(self.state),
                "--cwd",
                str(self.cwd),
                *extra,
            ],
            env=dict(self.env, TEST_MODE=mode),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.processes.append(proc)
        return proc

    def ready(self, exclude=()):
        end = time.monotonic() + 5
        while time.monotonic() < end:
            candidates = [
                p
                for p in self.state.glob("subagents/jobs/*/sessions/invocation.json")
                if p.parent not in exclude
            ]
            if candidates:
                try:
                    return candidates[-1], json.loads(candidates[-1].read_text())
                except ValueError:
                    pass
            time.sleep(0.01)
        self.fail("fake child did not become ready")

    def test_fixed_flash_flags_fresh_native_sessions_and_environment(self):
        first = self.run_job()
        second = self.run_job()
        self.assertNotEqual(first["jobid"], second["jobid"])
        self.assertNotEqual(first["artifacts"]["sessions"], second["artifacts"]["sessions"])
        session = Path(first["artifacts"]["sessions"])
        call = json.loads((session / "invocation.json").read_text())
        self.assertEqual(
            call["args"][:-1],
            [
                "--provider",
                "zai",
                "--model",
                "glm-5.3-flash",
                "--thinking",
                "high",
                "--print",
                "--mode",
                "json",
                "--",
            ],
        )
        self.assertIn("Inspect approved fixture", call["args"][-1])
        self.assertEqual(call["cwd"], str(self.cwd))
        self.assertEqual(call["env"]["PI_RE_CHILD"], "1")
        self.assertEqual(call["env"]["PI_RE_CONFIG"], str(self.config))
        self.assertEqual(call["env"]["PI_CODING_AGENT_DIR"], str(self.agent))
        self.assertEqual(call["env"]["PI_RE_CHILD_SESSION_DIR"], str(session))
        self.assertEqual(call["env"]["PI_CODING_AGENT_SESSION_DIR"], str(session))
        self.assertEqual(call["env"]["PI_PACKAGE_DIR"], "/reviewed/pi-package")
        self.assertEqual(call["env"]["TEST_PROFILE"], "preserved")
        for key in (
            "PI_SESSION_FILE",
            "PI_SESSION_ID",
            "PI_PROVIDER",
            "PI_MODEL",
            "PI_REASONING_LEVEL",
        ):
            self.assertNotIn(key, call["env"])
        self.assertEqual(self.env, self.original)
        self.assertTrue((session / "native.jsonl").is_file())

    def test_jsonl_authoritative_text_tools_and_usage(self):
        summary = self.run_job()
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["result"], "final\u2028line\u2029paragraph")
        self.assertNotIn("thinking", summary["result"])
        self.assertEqual(summary["usage"]["input"], 2)  # no duplicate agent_end accounting
        self.assertEqual(summary["usage"]["cost"]["total"], 0.01)
        tools = Path(summary["artifacts"]["tools"]).read_text()
        self.assertIn("tool private text", tools)
        self.assertIn("tool event text", tools)
        self.assertNotIn("tool private text", summary["result"])
        self.assertTrue(
            all(Path(p).is_relative_to(self.state) for p in summary["artifacts"].values())
        )

    def test_jsonl_fallback_errors_retries_partial_and_nonzero(self):
        for mode, status in (
            ("error", "error"),
            ("aborted", "error"),
            ("wrong-model", "error"),
            ("nonzero", "error"),
            ("agent-end", "ok"),
            ("malformed", "partial"),
            ("oversized-line", "partial"),
            ("delta", "error"),
            ("retry", "ok"),
        ):
            with self.subTest(mode=mode):
                summary = self.run_job(mode)
                self.assertEqual(summary["status"], status)
                if mode == "retry":
                    self.assertEqual(summary["result"], "retry success")
                    self.assertEqual(summary["error"], "")
                    self.assertEqual(summary["usage"]["input"], 4)
                if mode == "error":
                    self.assertEqual(summary["error"], "fixture provider failure")

    def test_bounded_json_summary_unicode_escaping_logs_and_private_artifacts(self):
        summary = self.run_job("huge")
        self.assertLessEqual(
            len(json.dumps(summary, ensure_ascii=False).encode()), helper.RESULT_BYTES
        )
        self.assertEqual(summary["status"], "partial")
        self.assertTrue(summary["resultTruncated"])
        self.assertTrue(summary["logTruncated"]["events"])
        self.assertTrue(summary["logTruncated"]["stderr"])
        self.assertLessEqual(Path(summary["artifacts"]["events"]).stat().st_size, helper.LOG_BYTES)
        self.assertLessEqual(
            Path(summary["artifacts"]["stderr"]).stat().st_size, helper.STDERR_BYTES
        )
        self.assertLessEqual(Path(summary["artifacts"]["result"]).stat().st_size, helper.TEXT_BYTES)
        self.assertNotIn("private diagnostics", json.dumps(summary))
        for path in self.state.rglob("*"):
            self.assertEqual(path.stat().st_uid, os.getuid())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0, str(path))

    def test_shell_prompt_and_foreign_file_syntax_are_inert(self):
        marker = self.root / "must-not-exist"
        task = f"@/foreign/session.jsonl\n/skill:evil\n--resume; touch {marker} $(false)"
        summary = self.run_job(task=task)
        call = json.loads((Path(summary["artifacts"]["sessions"]) / "invocation.json").read_text())
        self.assertTrue(call["args"][-1].startswith("Delegated RE task"))
        self.assertIn(task, call["args"][-1])
        self.assertFalse(marker.exists())
        self.assertEqual(Path(summary["artifacts"]["prompt"]).read_text(), task)

    def test_deadline_and_cancel_do_not_kill_unrelated_process(self):
        unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
        self.processes.append(unrelated)
        started = time.monotonic()
        summary = self.run_job("sleep", deadline=0.15)
        self.assertEqual(summary["status"], "timeout")
        self.assertLess(time.monotonic() - started, 2)
        self.assertIsNone(unrelated.poll())
        proc = self.cli("sleep")
        proc.stdin.write(b"approved fixture")
        proc.stdin.close()
        proc.stdin = None
        _, call = self.ready(exclude=(Path(summary["artifacts"]["sessions"]),))
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=4)
        self.assertEqual(json.loads(out)["status"], "cancelled")
        self.assertEqual(err, b"")
        self.assertIsNone(unrelated.poll())

    @staticmethod
    def assert_process_stopped(pid):
        status = Path(f"/proc/{pid}/stat")
        return not status.exists() or status.read_text().split(") ", 1)[1].startswith("Z ")

    def test_owned_descendants_are_stopped_on_cancellation(self):
        proc = self.cli("descendant")
        proc.stdin.write(b"owned fixture")
        proc.stdin.close()
        proc.stdin = None
        invocation, call = self.ready()
        pidfile = invocation.parent / "descendant.pid"
        end = time.monotonic() + 3
        while not pidfile.exists() and time.monotonic() < end:
            time.sleep(0.01)
        descendant = int(pidfile.read_text())
        proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=4)
        self.assertEqual(json.loads(out)["status"], "cancelled")
        self.assertTrue(self.assert_process_stopped(call["pid"]))
        end = time.monotonic() + 1
        while not self.assert_process_stopped(descendant) and time.monotonic() < end:
            time.sleep(0.01)
        self.assertTrue(self.assert_process_stopped(descendant))

    def test_parent_death_cancels_owned_child_and_records_summary(self):
        # The bridge is the helper's direct parent, not the fake model child.
        bridge = r"""import os,subprocess,sys,time
p=subprocess.Popen(sys.argv[1:],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
p.stdin.write(b"approved fixture");p.stdin.close()
time.sleep(60)
"""
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                bridge,
                sys.executable,
                str(HELPER),
                "--config",
                str(self.config),
                "--state-dir",
                str(self.state),
                "--cwd",
                str(self.cwd),
            ],
            env=dict(self.env, TEST_MODE="sleep"),
        )
        self.processes.append(proc)
        invocation, call = self.ready()
        proc.kill()
        proc.wait()
        summaryfile = invocation.parent.parent / "summary.json"
        end = time.monotonic() + 4
        summary = None
        while time.monotonic() < end:
            try:
                summary = json.loads(summaryfile.read_text())
                break
            except (OSError, ValueError):
                time.sleep(0.01)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["status"], "cancelled")
        self.assertTrue(self.assert_process_stopped(call["pid"]))

    def test_helper_sigkill_backstop_stops_direct_child(self):
        proc = self.cli("sleep")
        proc.stdin.write(b"approved fixture")
        proc.stdin.close()
        proc.stdin = None
        _, call = self.ready()
        proc.kill()
        proc.wait(timeout=2)
        end = time.monotonic() + 2
        while not self.assert_process_stopped(call["pid"]) and time.monotonic() < end:
            time.sleep(0.01)
        self.assertTrue(self.assert_process_stopped(call["pid"]))
        # SIGKILL releases the kernel slot even though it cannot publish a summary.
        self.assertEqual(self.run_job()["status"], "ok")

    def test_waitnowait_retains_leader_until_cleanup_prevents_pid_reuse(self):
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        self.processes.append(proc)
        end = time.monotonic() + 2
        while helper.child_running(proc) and time.monotonic() < end:
            time.sleep(0.01)
        self.assertFalse(helper.child_running(proc))
        self.assertIsNone(proc.returncode)  # not reaped by polling
        os.kill(proc.pid, 0)  # zombie retains PID until explicit group cleanup/wait
        proc.wait()

    def test_two_kernel_slots_reject_third_and_release(self):
        for _ in range(2):
            proc = self.cli("sleep")
            proc.stdin.write(b"approved fixture")
            proc.stdin.close()
            proc.stdin = None
        end = time.monotonic() + 5
        while (
            len(list(self.state.glob("subagents/jobs/*/sessions/invocation.json"))) < 2
            and time.monotonic() < end
        ):
            time.sleep(0.01)
        self.assertEqual(len(list(self.state.glob("subagents/jobs/*/sessions/invocation.json"))), 2)
        third = self.cli()
        out, _ = third.communicate(b"third", timeout=3)
        self.assertEqual(json.loads(out)["status"], "blocked")
        self.assertIn("two", json.loads(out)["error"])
        for proc in self.processes[:2]:
            proc.send_signal(signal.SIGTERM)
            proc.communicate(timeout=4)
        self.assertEqual(self.run_job()["status"], "ok")

    def test_unsafe_paths_profiles_children_and_task_limits_fail_closed(self):
        cases = [
            dict(state_dir=self.root / "foreign"),
            dict(cwd=Path("relative")),
            dict(cwd=self.root / "missing"),
            dict(task=""),
            dict(task="\0"),
            dict(task="漢" * 30000),
            dict(deadline=0),
            dict(deadline=181),
            dict(deadline=float("nan")),
            dict(env=dict(self.env, PI_RE_CHILD="1")),
            dict(env=dict(self.env, PI_RE_CONFIG="/foreign/config.json")),
            dict(env=dict(self.env, PI_CODING_AGENT_DIR="/foreign/coding")),
        ]
        for override in cases:
            args = dict(
                config_path=self.config,
                state_dir=self.state,
                cwd=self.cwd,
                task="task",
                env=self.env,
            )
            args.update(override)
            with self.subTest(override=list(override)), self.assertRaises(ValueError):
                helper.run_job(**args)
        self.assertFalse((self.root / "foreign").exists())

    def test_symlink_directory_and_hardlink_lock_rejected(self):
        self.state.parent.mkdir(parents=True)
        target = self.root / "foreign-state"
        target.mkdir(mode=0o700)
        self.state.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.run_job()
        self.state.unlink()
        helper.private_directory(self.state)
        slots = self.state / "subagents"
        helper.private_directory(slots)
        original = self.root / "foreign-lock"
        original.write_text("unchanged")
        original.chmod(0o600)
        os.link(original, slots / "slot-0.lock")
        with self.assertRaises(ValueError):
            self.run_job()
        self.assertEqual(original.read_text(), "unchanged")

    def test_nonprivate_directory_and_symlink_file_rejected(self):
        helper.private_directory(self.state)
        slots = self.state / "subagents"
        slots.mkdir(mode=0o755)
        with self.assertRaises(ValueError):
            self.run_job()
        slots.chmod(0o700)
        target = self.root / "foreign-file"
        target.write_text("do not touch")
        (slots / "slot-0.lock").symlink_to(target)
        with self.assertRaises(ValueError):
            self.run_job()
        self.assertEqual(target.read_text(), "do not touch")

    def test_replaced_artifact_rejected_before_publication(self):
        real_popen = subprocess.Popen
        foreign = self.root / "foreign-artifact"
        foreign.write_text("foreign data")
        foreign.chmod(0o600)

        def tamper(*args, **kw):
            proc = real_popen(*args, **kw)
            job = next(self.state.glob("subagents/jobs/*"))
            (job / "result.txt").unlink()
            os.link(foreign, job / "result.txt")
            return proc

        with (
            patch.object(helper.subprocess, "Popen", side_effect=tamper),
            self.assertRaises(ValueError),
        ):
            self.run_job()
        self.assertEqual(foreign.read_text(), "foreign data")

    def test_native_session_symlink_and_hardlink_artifacts_rejected(self):
        foreign = self.root / "foreign-native.jsonl"
        foreign.write_text("unchanged")
        foreign.chmod(0o600)
        self.env["TEST_UNSAFE_TARGET"] = str(foreign)
        for mode in ("unsafe-session-symlink", "unsafe-session-hardlink"):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.run_job(mode)
        self.assertEqual(foreign.read_text(), "unchanged")

    def test_failed_exec_has_stable_job_summary(self):
        self.config.write_text(
            json.dumps({"python": "/nonexistent/python", "resources": str(self.resources)})
        )
        summary = self.run_job()
        self.assertEqual(summary["status"], "error")
        self.assertIsNotNone(summary["jobid"])
        self.assertIsNone(summary["exitCode"])
        self.assertTrue(Path(summary["artifacts"]["summary"]).is_file())

    def test_cli_stdin_summary_and_no_resume_interface(self):
        proc = self.cli()
        out, err = proc.communicate(b"CLI task", timeout=4)
        self.assertEqual(json.loads(out)["status"], "ok")
        self.assertEqual(err, b"")
        proc = self.cli(extra=("--session", "/foreign/session"))
        out, err = proc.communicate(b"task", timeout=4)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(b"unrecognized arguments", err)
        proc = self.cli()
        out, _ = proc.communicate(b"x" * (helper.PROMPT_BYTES + 1), timeout=4)
        self.assertEqual(json.loads(out)["status"], "blocked")

    @unittest.skipUnless(
        shutil.which("bun"), "Bun is needed only for the optional offline extension harness"
    )
    def test_extension_execution_registration_child_guard_and_cancel(self):
        # Exercise our real TS execute method with an API/schema stub and real fake Python
        # launcher. Installed Pi help-load is a separate API/import smoke check.
        (self.resources / "subagent.py").write_text(HELPER.read_text())
        harness = self.root / "extension-test.ts"
        harness.write_text(r"""
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
let source = readFileSync(process.argv[2], "utf8");
source = source.replace('import { Type } from "@earendil-works/pi-ai";',
  `const Type = {Object: (properties, options) => ({properties, ...options}), String: (options) => options, Optional: (schema) => schema};`);
const transpiled = new Bun.Transpiler({loader: "ts"}).transformSync(source);
const modulePath = process.argv[1] + ".mjs";
await Bun.write(modulePath, transpiled);
const factory = (await import(modulePath)).default;
let tool;
const api = {on: () => {}, registerTool: (value) => {tool = value;}};
process.env.PI_RE_CHILD = "1";
factory(api);
assert.equal(tool, undefined);
delete process.env.PI_RE_CHILD;
factory(api);
assert.equal(tool.name, "re_subagent");
assert.deepEqual(Object.keys(tool.parameters.properties), ["task", "cwd"]);
assert.equal(tool.parameters.additionalProperties, false);
let result = await tool.execute("fixture", {task: "approved task"}, undefined, undefined, {cwd: process.argv[3]});
assert.equal(result.details.status, "ok");
assert.equal(result.details.model, "glm-5.3-flash");
assert.equal(result.isError, false);
assert(Buffer.byteLength(result.content[0].text) <= 16384);
assert.equal(result.usage.input, 2);
const already = new AbortController(); already.abort();
await assert.rejects(tool.execute("cancelled", {task: "task"}, already.signal, undefined, {cwd: process.argv[3]}), /cancelled/);
process.env.TEST_MODE = "sleep";
const controllers = [new AbortController(), new AbortController()];
const calls = controllers.map(c => tool.execute("fixture", {task: "authorized fixture"}, c.signal, undefined, {cwd: process.argv[3]}));
// Wait for both helpers to establish their owned child fixtures; not a subagent-harness poll.
const {globSync} = await import("node:fs");
const directory = process.env.XDG_STATE_HOME + "/pi-re/subagents/jobs/*/sessions/invocation.json";
const stop = Date.now() + 4000;
while (globSync(directory).length < 3 && Date.now() < stop) await Bun.sleep(10);
assert.equal(globSync(directory).length, 3);
await assert.rejects(tool.execute("third", {task: "task"}, undefined, undefined, {cwd: process.argv[3]}), /two/);
controllers.forEach(c => c.abort());
result = await Promise.all(calls);
assert(result.every(r => r.details.status === "cancelled" && r.isError));
console.log("offline extension harness passed");
""")
        proc = subprocess.run(
            [
                shutil.which("bun"),
                str(harness),
                str(ROOT / "home-manager/modules/ai/pi-re/flash-subagent.ts"),
                str(self.cwd),
            ],
            env=self.env,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertIn(b"offline extension harness passed", proc.stdout)

    def test_lf_framing_chunk_boundaries_malformed_records_and_tool_budget(self):
        tools = io.BytesIO()
        events = helper.Events(tools)
        records = [
            None,
            [],
            {"type": "message_end", "message": None},
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "unicode\u2028text\u2029"}],
                    "stopReason": "stop",
                },
            },
        ]
        raw = b"\r\n" + b"\n".join(json.dumps(r, ensure_ascii=False).encode() for r in records)
        for index in range(0, len(raw), 3):
            events.feed(raw[index : index + 3])
        events.finish()
        self.assertEqual(events.final, "unicode\u2028text\u2029")
        self.assertTrue(events.partial)
        for _ in range(10):
            events.tool_text([{"type": "text", "text": "x" * 50000}])
        self.assertLessEqual(len(tools.getvalue()), helper.TEXT_BYTES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
