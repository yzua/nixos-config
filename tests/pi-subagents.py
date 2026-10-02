#!/usr/bin/env python3
"""Offline regressions through the installed Pi loader; no model or auth access."""

import json
import os
import select
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "pi-subagents"
SOURCE = REPO / "home-manager/modules/ai/pi/extensions/interactive-subagents/pi-extension/subagents"
PI = os.environ.get("PI_BIN", shutil.which("pi"))

FAKE_TMUX = """#!/usr/bin/env python3
import json, os, shlex, sys, time
from pathlib import Path
root = Path(os.environ['PI_TEST_ROOT'])
args = sys.argv[1:]
def write_lease(session):
    owner = json.loads(Path(str(session) + '.owner.json').read_text())
    stat = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    Path(str(session) + '.writer.json').write_text(json.dumps({
        'version': 1, 'sessionFile': str(session.resolve()),
        'runningChildId': owner['run']['id'], 'token': owner['token'],
        'pid': os.getpid(), 'startTime': stat[19],
        'machineId': Path('/etc/machine-id').read_text().strip(),
        'bootId': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'pidNamespace': os.readlink('/proc/self/ns/pid')}))
if args[0] == 'writer-lease':
    # The shim is a real short-lived writer; after return this lease proves death.
    write_lease(Path(args[1]))
    sys.exit(0)
with (root / 'tmux-calls').open('a') as calls:
    calls.write(json.dumps(args) + '\\n')
modefile = root / 'tmux-mode'
mode = modefile.read_text() if modefile.exists() else 'healthy'
if args[0] == 'kill-pane':
    (root / f'closed-{args[2]}').write_text('closed')
    if mode == 'managed-cleanup-fault':
        command = Path((root / f'command-{args[2]}').read_text()).read_text().splitlines()[-1]
        parts = shlex.split(command)
        owner = Path(parts[parts.index('--session') + 1] + '.owner.json')
        lock = Path(str(owner).removesuffix('.owner.json') + '.owner.lock')
        # kill-pane runs synchronously inside the ownership critical section.
        # No late writer or FIFO is needed to force the real rmdir failure.
        (lock / 'blocked').write_text('filesystem failure fixture')
if args[0] == 'send-keys':
    if mode == 'send-failure':
        if '-l' in args and args[-1].startswith('bash '):
            command = Path(shlex.split(args[-1])[1]).read_text().splitlines()[-1]
            parts = shlex.split(command)
            write_lease(Path(parts[parts.index('--session') + 1]))
        sys.exit(1)
    pane = args[2]
    command_file = root / f'command-{pane}'
    if '-l' in args and args[-1].startswith('bash '):
        command_file.write_text(shlex.split(args[-1])[1])
    elif args[-1] == 'Enter' and mode.startswith('managed') and command_file.exists():
        command = Path(command_file.read_text()).read_text().splitlines()[-1]
        parts = shlex.split(command)
        session = Path(parts[parts.index('--session') + 1])
        if not session.exists():
            session.write_text(json.dumps({'type': 'session', 'id': 'managed-child',
                                          'version': 3, 'cwd': str(root)}) + '\\n')
        counter = root / 'managed-runs'
        n = int(counter.read_text()) + 1 if counter.exists() else 1
        counter.write_text(str(n))
        if mode == 'managed-invalid':
            with session.open('a') as stream:
                stream.write('invalid json\\n')
        elif mode != 'managed-empty':
            message = {'type': 'message', 'message': {'role': 'assistant',
                       'content': [{'type': 'text', 'text': f'RUN_{n}'}]}}
            with session.open('a') as stream:
                stream.write(json.dumps(message) + '\\n')
        if mode == 'managed-error':
            Path(str(session) + '.exit').write_text(json.dumps({
                'type': 'error', 'errorMessage': 'OFFLINE_PROVIDER_FAILURE'}))
        write_lease(session)
        if mode != 'managed-live':
            (root / f'done-{pane}').write_text('done')
if args[0] == 'split-window':
    counter = root / 'pane-count'
    n = int(counter.read_text()) + 1 if counter.exists() else 1
    counter.write_text(str(n))
    print(f'%{n}')
elif args[0] == 'capture-pane':
    if (root / 'capture-delay').exists():
        time.sleep(float((root / 'capture-delay').read_text()))
    pane = args[args.index('-t') + 1]
    if (root / f'closed-{pane}').exists():
        sys.exit(1)
    if mode in ('missing', 'late-sidecar', 'capture-error', 'unavailable'):
        sys.exit(1)
    if mode == 'transient':
        counter = root / 'capture-count'
        n = int(counter.read_text()) + 1 if counter.exists() else 1
        counter.write_text(str(n))
        if n == 1:
            sys.exit(1)
        print('__SUBAGENT_DONE_0__')
    elif mode == 'sentinel' or (root / f'done-{args[args.index("-t") + 1]}').exists():
        print('__SUBAGENT_DONE_0__')
elif args[0] == 'display-message':
    if mode in ('missing', 'late-sidecar'):
        sys.exit(1)
    print('%99')
elif args[0] == 'list-panes':
    if mode == 'unavailable':
        sys.exit(1)
    if mode not in ('missing', 'late-sidecar'):
        print('%99')
        counter = root / 'pane-count'
        for n in range(1, int(counter.read_text()) + 1 if counter.exists() else 1):
            if not (root / f'closed-%{n}').exists():
                print(f'%{n}')
"""


def offline_environment():
    """Keep fixture processes away from the caller's live multiplexer/children."""
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PI_SUBAGENT", "HERDR_")) and key not in {"TMUX", "TMUX_PANE"}
    }


class PiRegressions(unittest.TestCase):
    def setUp(self):
        if not PI:
            self.fail("Pi is required; install it or set PI_BIN to its executable")
        self.tmp = tempfile.TemporaryDirectory(prefix="pi-subagents-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.agent = self.root / "agent"
        self.agent.mkdir()
        (self.agent / "settings.json").write_text(
            json.dumps(
                {
                    "retry": {"enabled": True, "maxRetries": 1, "baseDelayMs": 1},
                    "compaction": {"enabled": False},
                }
            )
        )
        self.env = offline_environment()
        self.env.update(
            PI_CODING_AGENT_DIR=str(self.agent),
            PI_TEST_ROOT=str(self.root),
            PI_TEST_EVENTS=str(self.root / "events"),
            PI_SUBAGENT_SESSION=str(self.root / "child.jsonl"),
            PI_SUBAGENT_AUTO_EXIT="1",
        )

    def start(self, scenario, fixture="mock-provider.ts", done=True):
        self.env["PI_TEST_SCENARIO"] = scenario
        args = [
            PI,
            "--mode",
            "rpc",
            "--approve",
            "--no-extensions",
            "--no-skills",
            "--no-prompt-templates",
            "--provider",
            "pi-test",
            "--model",
            "offline",
            "--session",
            str(self.root / "child.jsonl"),
            "-e",
            str(FIXTURES / fixture),
        ]
        if fixture != "mock-provider.ts":
            args += ["-e", str(FIXTURES / "mock-provider.ts")]
        if done:
            args += ["-e", str(SOURCE / "subagent-done.ts")]
        process = subprocess.Popen(
            args,
            cwd=self.root,
            env=self.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.addCleanup(self.stop, process)
        return process

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()

    @staticmethod
    def prompt(process, text, streaming_behavior=None):
        command = {"type": "prompt", "message": text}
        if streaming_behavior:
            command["streamingBehavior"] = streaming_behavior
        process.stdin.write(json.dumps(command).encode() + b"\n")
        process.stdin.flush()

    def events(self):
        path = self.root / "events"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def wait_for(self, predicate, process, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            if process.poll() is not None:
                output, error = process.communicate()
                self.fail(
                    f"Pi exited before expected result: {error.decode()} {output.decode()[-1500:]}"
                )
            time.sleep(0.01)
        self.fail("Pi did not produce the expected result before timeout")

    def finish(self, process):
        # communicate() closes stdin, which RPC treats as shutdown. Drain its
        # output while leaving stdin open until the child requests shutdown.
        output = bytearray()
        deadline = time.monotonic() + 8
        while process.poll() is None and time.monotonic() < deadline:
            ready, _, _ = select.select([process.stdout], [], [], 0.01)
            if ready:
                output.extend(os.read(process.stdout.fileno(), 65536))
        self.assertIsNotNone(process.poll(), "Pi did not auto-exit after finishing")
        remaining, error = process.communicate(timeout=2)
        output.extend(remaining)
        self.assertEqual(process.returncode, 0, error.decode())
        self.assertNotIn(b"Failed to load extension", error)
        return bytes(output)

    def test_recovered_retry_does_not_publish_failure(self):
        process = self.start("recovered")
        self.prompt(process, "fixture")
        output = self.finish(process)
        self.assertTrue(b"OFFLINE_RECOVERED" in output, f"retry did not recover: {self.events()}")
        self.assertEqual([e["event"] for e in self.events()].count("agent_end"), 2)
        self.assertFalse(
            (self.root / "child.jsonl.exit").exists(), "recovered retry published an error sidecar"
        )
        self.assertFalse(any(e["sidecar"] for e in self.events()), self.events())

    def test_exhausted_retry_publishes_failure_only_after_settled(self):
        process = self.start("exhausted")
        self.prompt(process, "fixture")
        self.finish(process)
        events = self.events()
        self.assertEqual([e["event"] for e in events].count("agent_end"), 2)
        self.assertFalse(
            any(e["sidecar"] for e in events if e["event"] != "session_shutdown"), events
        )
        error = json.loads((self.root / "child.jsonl.exit").read_text())
        self.assertEqual(error["type"], "error")
        self.assertIn("overloaded_error", error["errorMessage"])

    def assert_parked_then_resumed(self, scenario):
        process = self.start(scenario)
        self.prompt(process, "fixture")
        self.wait_for(lambda: any(e["event"] == "agent_settled" for e in self.events()), process)
        time.sleep(0.05)
        self.assertIsNone(
            process.poll(), "child exited while waiting for parent or nested children"
        )
        self.assertFalse((self.root / "child.jsonl.exit").exists())
        if scenario == "question":
            self.assertTrue((self.root / "child.jsonl.ask").exists())
        self.prompt(process, "parent followup")
        self.assertIn(b"OFFLINE_RECOVERED", self.finish(process))

    def test_pending_question_keeps_child_open(self):
        self.assert_parked_then_resumed("question")

    def test_nested_children_keep_child_open(self):
        self.assert_parked_then_resumed("nested")

    def test_queued_followup_finishes_before_auto_exit(self):
        process = self.start("queued")
        self.prompt(process, "initial fixture")
        self.wait_for(lambda: any(e["event"] == "provider_call:1" for e in self.events()), process)
        self.prompt(process, "queued continuation", "followUp")
        self.finish(process)
        self.assertIn("provider_call:2", [event["event"] for event in self.events()])

    def probes(self, scenario):
        bindir = self.root / "bin"
        bindir.mkdir(exist_ok=True)
        shim = bindir / "tmux"
        shim.write_text(FAKE_TMUX)
        shim.chmod(0o755)
        forbidden = bindir / "herdr"
        forbidden.write_text(
            "#!/usr/bin/env bash\necho 'Offline fixture reached Herdr' >&2\nexit 1\n"
        )
        forbidden.chmod(0o755)
        if not hasattr(self, "mux_endpoint"):
            self.mux_endpoint = socket.socket(socket.AF_UNIX)
            self.addCleanup(self.mux_endpoint.close)
            self.mux_endpoint.bind(str(self.root / "tmux.sock"))
        self.env.update(
            PATH=f"{bindir}:{self.env['PATH']}",
            TMUX=f"{self.root / 'tmux.sock'},123,0",
            TMUX_PANE="%0",
            PI_SUBAGENT_SHELL_READY_DELAY_MS="20",
        )
        agents = self.agent / "agents"
        agents.mkdir(exist_ok=True)
        (agents / "fixture.md").write_text(
            "---\nname: fixture\ntools: read\nauto-exit: true\n---\nOffline fixture role.\n"
        )
        (self.root / "parent.jsonl").write_text(
            json.dumps({"type": "session", "id": "fixture-parent", "version": 3}) + "\n"
        )
        fixture = (
            "managed-run-probes.ts"
            if scenario
            in {
                "lifecycle",
                "disposal",
                "completion-errors",
                "cleanup-errors",
                "ownership",
                "ownership-park",
                "ownership-restart",
                "ownership-refusals",
            }
            else "runtime-probes.ts"
        )
        process = self.start(scenario, fixture, done=False)
        # These probes run during session_start without starting an agent loop.
        # Wait for their output, then close RPC explicitly.
        self.wait_for(lambda: (self.root / "results.json").exists(), process, timeout=15)
        _, error = process.communicate(timeout=2)
        self.assertEqual(process.returncode, 0, error.decode())
        results = json.loads((self.root / "results.json").read_text())
        self.assertNotIn("failure", results, results)
        return results

    def test_offline_environment_drops_inherited_multiplexer_and_child_state(self):
        inherited = {
            "HERDR_ENV": "1",
            "HERDR_SOCKET_PATH": "/fixture/live-herdr.sock",
            "HERDR_PANE_ID": "w1:p1",
            "HERDR_FUTURE_SETTING": "must-not-leak",
            "TMUX": "live-server",
            "TMUX_PANE": "%99",
            "PI_SUBAGENT_SESSION": "/fixture/live-child.jsonl",
            "PI_TEST_KEEP": "fixture",
        }
        with patch.dict(os.environ, inherited):
            isolated = offline_environment()
        self.assertEqual(isolated["PI_TEST_KEEP"], "fixture")
        self.assertFalse(any(key.startswith(("HERDR_", "PI_SUBAGENT")) for key in isolated))
        self.assertNotIn("TMUX", isolated)
        self.assertNotIn("TMUX_PANE", isolated)

    def test_missing_pane_reports_failure_and_late_sidecar_wins(self):
        results = self.probes("panes")
        self.assertEqual(results["missing"].get("reason"), "error", results)
        self.assertIn("pane", results["missing"]["errorMessage"].lower())
        self.assertLess(results["missing"]["elapsedMs"], 3000)
        self.assertEqual(results["unavailable"].get("reason"), "error", results)
        self.assertIn("tmux is unavailable", results["unavailable"]["errorMessage"])
        self.assertEqual(results["late-sidecar"]["reason"], "done", results)
        for mode in ["transient", "sentinel"]:
            self.assertEqual(results[mode]["reason"], "sentinel", results)
            self.assertEqual(results[mode]["exitCode"], 0)
        self.assertIn("Aborted", results["healthy"]["error"])
        self.assertIn("Aborted", results["capture-error"]["error"])

    def test_explicit_names_reserve_and_preserve_finished_handles(self):
        results = self.probes("names")
        self.assertEqual(
            [spawn["name"] for spawn in results["parallel"]], ["duplicate", "duplicate-2"]
        )
        self.assertEqual(results["finishedName"], "duplicate-3")
        first = results["parallel"][0]
        self.assertEqual(
            results["registryBeforeResume"]["duplicate"]["sessionFile"], first["sessionFile"]
        )
        self.assertEqual(results["resume"]["name"], "duplicate", results)
        self.assertEqual(results["reservations"], [], results)

    def test_managed_runs_complete_and_resume_only_new_output(self):
        results = self.probes("lifecycle")
        self.assertEqual([r["details"]["name"] for r in results["delivered"]], ["managed"] * 3)
        for result, summary in zip(
            results["delivered"],
            ["RUN_1", "RUN_2", "Resumed session exited without new output"],
            strict=True,
        ):
            self.assertIn(summary, result["content"])
            self.assertEqual(result["details"]["exitCode"], 0)
            self.assertEqual(result["options"], {"triggerTurn": True, "deliverAs": "steer"})
        self.assertNotIn("RUN_1", results["delivered"][1]["content"])
        self.assertNotIn("RUN_2", results["delivered"][2]["content"])
        self.assertEqual(results["refusedPanes"], results["panesBeforeRefusal"])
        self.assertIn("Cannot safely resume", results["missingLoadout"]["error"])
        self.assertEqual(results["nextName"], "managed-2")
        self.assertEqual(set(results["closedPanes"]), {"%1", "%2", "%3"})
        for command in results["commands"]:
            self.assertIn("pi --approve", command)
            self.assertIn("--no-extensions", command)
            self.assertIn(
                "--tools 'read,subagent,subagent_message,subagents_list,ask_question'", command
            )
            self.assertIn("--model 'offline-fixed'", command)
            self.assertIn("--thinking 'high'", command)
            self.assertIn("--system-prompt", command)
            self.assertIn("PI_SUBAGENT_ALLOWED='scout'", command)
            self.assertIn("PI_SUBAGENT_AGENT='fixture'", command)
            self.assertIn("PI_SUBAGENT_SURFACE=", command)
        self.assertNotIn("PI_SUBAGENT_AUTO_EXIT=", results["commands"][0])
        self.assertTrue(
            all("PI_SUBAGENT_AUTO_EXIT='1'" in command for command in results["commands"][1:])
        )
        self.assertEqual(results["identities"], ["Fixed role."] * 3)

    def test_disposed_runtime_stops_delivery_without_terminating_child(self):
        results = self.probes("disposal")
        self.assertEqual(len(results["delivered"]), 1, results)
        self.assertEqual(results["delivered"][0]["details"]["name"], "replacement")
        self.assertEqual(results["closedPanes"], ["%2"])
        self.assertEqual(results["postShutdownWidgets"], 0)
        self.assertEqual(results["questionWakeups"], 0, results)

    def test_detached_child_keeps_exclusive_session_ownership(self):
        results = self.probes("ownership")
        self.assertEqual(results["panesAfterDetachedFollowup"], "1", results)
        self.assertEqual(results["detachedFollowup"]["status"], "steered", results)
        self.assertTrue(results["claimSurvives"], results)
        self.assertEqual(
            sum(r.get("status") == "started" for r in results["parallelResumes"]), 1, results
        )
        self.assertTrue(results["ownerAfterCompletion"]["delivered"], results)
        self.assertIn("send-keys", results["failedResume"])
        self.assertTrue(results["ownerAfterFailure"]["delivered"], results)
        self.assertEqual(results["retry"]["status"], "started", results)
        self.assertEqual(len(results["delivered"]), 3, results)
        for record, output in zip(results["delivered"], ["RUN_1", "RUN_2", "RUN_3"], strict=True):
            self.assertIn(output, record["content"])

    def test_ownership_survives_parent_process_restart_and_closed_pane_is_resumable(self):
        parked = self.probes("ownership-park")
        (self.root / "results.json").unlink()
        results = self.probes("ownership-restart")
        self.assertTrue(parked["claimSurvives"], parked)
        self.assertEqual(results["liveFollowup"]["status"], "steered", results)
        self.assertEqual(results["panesAfterLiveFollowup"], "1", results)
        self.assertEqual(results["closedPaneResume"]["status"], "started", results)
        self.assertEqual(len(results["delivered"]), 1, results)
        self.assertEqual(results["delivered"][0]["details"]["exitCode"], 0, results)
        self.assertIn("RUN_2", results["delivered"][0]["content"])
        self.assertNotIn("RUN_1", results["delivered"][0]["content"])
        self.assertTrue(results["ownerAfterCompletion"]["delivered"], results)

    def test_unknown_or_unmonitorable_child_ownership_fails_closed(self):
        results = self.probes("ownership-refusals")
        for case in ["corrupt", "wrongMux", "busy", "unavailable", "captureFailure", "slowCapture"]:
            self.assertRegex(results[case]["error"], r"Cannot safely (?:resume|recall)", results)
        self.assertLess(results["slowCaptureMs"], 3200, results)
        self.assertEqual(results["panes"], "1", results)
        self.assertTrue(results["claimPreserved"], results)
        self.assertEqual(results["closedPanes"], [], results)
        self.assertEqual(results["delivered"], [], results)

    def test_completion_cleanup_failure_delivers_result_and_fails_closed(self):
        results = self.probes("cleanup-errors")
        self.assertEqual(len(results["delivered"]), 1, results)
        self.assertEqual(results["delivered"][0]["details"]["exitCode"], 0, results)
        self.assertEqual(results["unhandled"], [], results)
        self.assertTrue(results["lockRetained"], results)
        self.assertIn("Cannot safely resume", results["retry"]["error"], results)

    def test_live_failures_and_legacy_cancellation_deliver_once_and_cleanup(self):
        results = self.probes("completion-errors")
        self.assertEqual(len(results["delivered"]), 3, results)
        provider, extraction, cancellation = results["delivered"]
        self.assertEqual(provider["details"]["errorMessage"], "OFFLINE_PROVIDER_FAILURE")
        self.assertEqual(provider["details"]["exitCode"], 1)
        self.assertEqual(extraction["details"]["exitCode"], 1)
        self.assertIn("Subagent error:", extraction["content"])
        self.assertEqual(
            results["deliveryAttempts"],
            ["provider-error", "extraction-error", "delivery-error", "cancelled"],
        )
        self.assertTrue(results["throwingOwner"]["delivered"], results)
        self.assertEqual(results["throwingRecall"], None, results)
        self.assertIn("Subagent cancelled.", cancellation["content"])
        self.assertEqual(cancellation["details"]["exitCode"], 1)
        self.assertEqual(results["closedPanes"], ["%1", "%2", "%3", "%4"])

    def test_failed_launch_releases_pane_and_name(self):
        results = self.probes("launch-failure")
        self.assertIn("send-keys", results["launchError"])
        self.assertEqual(results["retry"]["name"], "retryable")
        self.assertEqual(results["closedPanes"], ["%1", "%2"])

    def test_spawn_and_resume_apply_project_trust(self):
        results = self.probes("trust")
        for command in [*results["spawnCommands"], results["resumeCommand"]]:
            self.assertIn("pi --approve", command)
            self.assertIn("--no-extensions", command)
            self.assertIn("--tools 'read,ask_question'", command)
        self.assertTrue(results["loadoutExists"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
