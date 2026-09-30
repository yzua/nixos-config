#!/usr/bin/env python3
"""Exercise the voice command interface with fake executables and real flock.

Run: python3 tests/voice-action.py
Only the external commands are substituted; runtime/state directories are real
and private. No daemon mutations, notifications, or model calls leave the test.
"""

import json
import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ACTION = REPO / "home-manager/modules/ai/voice/action.sh"
FAKE = REPO / "tests/voice-action.fake.py"


class VoiceAction(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="voice-action-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("runtime", "state", "bin", "fake", "home"):
            (self.root / name).mkdir(mode=0o700)
        self.fake = self.root / "fake"
        (self.fake / "daemon.json").write_text('{"state":"idle","target":null}')
        (self.fake / "transcript").write_text("Open the browser")
        for name in ("voxtype", "pi", "notify-send"):
            (self.root / "bin" / name).symlink_to(FAKE)
        self.env = dict(
            os.environ,
            PATH=f"{self.root / 'bin'}:{os.environ['PATH']}",
            HOME=str(self.root / "home"),
            XDG_RUNTIME_DIR=str(self.root / "runtime"),
            XDG_STATE_HOME=str(self.root / "state"),
            VOICE_FAKE_DIR=str(self.fake),
            VOICE_ACTION_PROMPT=str(REPO / "home-manager/modules/ai/voice/action.md"),
        )
        self.processes = []
        self.addCleanup(self.stop_processes)

    def stop_processes(self):
        for hold in self.fake.glob("hold-*"):
            hold.unlink(missing_ok=True)
        for process in self.processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate()

    def launch(self, command="toggle"):
        process = subprocess.Popen(
            ["bash", str(ACTION), command],
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        self.processes.append(process)
        return process

    def finish(self, process, expected=0):
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, expected, stdout + stderr)

    def command(self, command="toggle", expected=0):
        self.finish(self.launch(command), expected)

    def events(self, kind):
        path = self.fake / "events.jsonl"
        return (
            [e for line in path.read_text().splitlines() if (e := json.loads(line))["kind"] == kind]
            if path.exists()
            else []
        )

    def ready(self, name):
        deadline = time.monotonic() + 5
        while not (self.fake / (name + "-ready")).exists():
            if time.monotonic() > deadline:
                self.fail("fake command did not reach " + name)
            time.sleep(0.01)

    def hold(self, name):
        (self.fake / ("hold-" + name)).touch()

    def release(self, name):
        (self.fake / ("hold-" + name)).unlink()

    def test_cancel_then_dictation_cannot_be_mistaken_for_action(self):
        self.command()
        self.command("cancel")
        self.command("dictation-toggle")
        self.command()  # Action on ordinary recording remains cancel-only.
        self.assertEqual(self.events("submitted"), [])
        self.assertEqual(self.events("paste"), [])
        self.command("dictation-toggle")
        self.command("dictation-toggle")
        self.assertEqual(self.events("paste")[0]["text"], "Ordinary dictation")

    def test_reset_discards_transcription_not_yet_submitted(self):
        self.command()
        self.hold("transcription")
        worker = self.launch()
        self.ready("transcription")
        self.command("reset")
        self.release("transcription")
        self.finish(worker)
        self.assertEqual(self.events("submitted"), [])
        self.command()
        self.command()
        self.assertEqual(self.events("request")[0]["text"], "Open the browser")

    def test_reset_and_cancel_leave_submitted_pi_in_old_context(self):
        self.command()
        self.hold("pi")
        worker = self.launch()
        self.ready("pi")
        old_session = self.events("submitted")[0]["session"]
        self.command("reset")
        self.command("dictation-toggle")  # Dictation can run independently of Pi.
        self.command("cancel")
        self.command("dictation-toggle")
        self.command("dictation-toggle")
        self.assertEqual(self.events("paste")[0]["text"], "Ordinary dictation")
        self.command()  # Busy action toggle cannot clear the running attachment.
        self.release("pi")
        self.finish(worker)
        self.assertEqual(self.events("request")[0]["text"], "Open the browser")
        self.assertEqual(self.events("request")[0]["session"], old_session)
        self.command()
        self.command()
        self.assertNotEqual(self.events("request")[1]["session"], old_session)

    def test_failed_cancel_cannot_resurrect_discarded_action(self):
        self.command()
        target = Path(self.events("recording")[0]["target"])
        (self.fake / "fail-cancel").touch()
        self.command("cancel", expected=1)
        (self.fake / "fail-cancel").unlink()
        self.command()  # Even if cancellation failed, this is not an action now.
        self.assertEqual(self.events("submitted"), [])
        self.assertFalse(target.exists(), "discarded transcript must be cleaned up")
        self.command()
        self.command()
        self.assertEqual(len(self.events("request")), 1)

    def test_failed_cancel_during_transcription_retains_ownership_until_retry(self):
        self.command()
        target = Path(self.events("recording")[0]["target"])
        self.hold("transcription")
        worker = self.launch()
        self.ready("transcription")
        (self.fake / "fail-cancel").touch()
        self.command("cancel", expected=1)
        self.finish(worker)
        self.assertTrue(target.parent.exists(), "daemon still owns its output directory")
        self.command("dictation-toggle", expected=1)
        self.assertEqual(self.events("submitted"), [])
        self.assertEqual(self.events("paste"), [])
        (self.fake / "fail-cancel").unlink()
        self.command("dictation-toggle")  # Retry discard, not ordinary stop/paste.
        self.assertFalse(target.parent.exists())
        self.release("transcription")
        self.command("dictation-toggle")
        self.command("dictation-toggle")
        self.assertEqual(self.events("paste")[0]["text"], "Ordinary dictation")

    def test_killed_transcription_wrapper_can_be_discarded_without_orphan_output(self):
        self.command()
        target = Path(self.events("recording")[0]["target"])
        self.hold("transcription")
        worker = self.launch()
        self.ready("transcription")
        os.kill(worker.pid, signal.SIGKILL)
        worker.wait(timeout=5)
        self.command("cancel")
        self.release("transcription")
        worker.communicate(timeout=5)
        self.assertEqual(self.events("submitted"), [])
        self.command("dictation-toggle")  # Reconcile after all surviving children finish.
        self.assertFalse(target.parent.exists())
        self.command("dictation-toggle")
        self.assertEqual(self.events("paste")[0]["text"], "Ordinary dictation")

    def test_pinned_daemon_clears_late_cancel_trigger_at_next_capture_start(self):
        self.command()
        self.hold("transcription")
        worker = self.launch()
        self.ready("transcription")
        (self.fake / "race-cancel-completion").touch()
        self.command("reset")  # Must not wait for a starved idle sweep.
        self.command("dictation-toggle")
        self.finish(worker)
        self.release("transcription")
        self.assertEqual(self.events("submitted"), [])
        self.assertEqual(len(self.events("cancel-after-completion")), 1)
        self.assertEqual(len(self.events("cancel-trigger-cleared-at-start")), 1)
        self.command("dictation-toggle")
        self.assertEqual(self.events("paste")[0]["text"], "Ordinary dictation")

    def test_ordinary_toggle_discards_action_recording_without_paste(self):
        self.command()
        self.command("dictation-toggle")
        self.assertEqual(self.events("paste"), [])
        self.assertEqual(self.events("submitted"), [])
        self.command("dictation-toggle")
        self.command("dictation-toggle")
        self.assertEqual(self.events("paste")[0]["text"], "Ordinary dictation")
        self.command()
        self.command()
        self.assertEqual(len(self.events("request")), 1)

    def test_cancel_and_ordinary_toggle_discard_transcription(self):
        for command in ("cancel", "dictation-toggle"):
            with self.subTest(command=command):
                (self.fake / "transcription-ready").unlink(missing_ok=True)
                self.command()
                self.hold("transcription")
                worker = self.launch()
                self.ready("transcription")
                self.command(command)
                self.command("dictation-toggle")  # Can restart before old worker exits.
                self.finish(worker)
                self.release("transcription")
                self.assertEqual(self.events("submitted"), [])
                self.command("dictation-toggle")
        self.assertEqual(len(self.events("paste")), 2)

    def test_empty_and_failed_transcriptions_clean_up_and_keep_session(self):
        self.command()
        self.command()
        first = self.events("request")[0]
        for text, fails in (("  \n\t", False), ("Discard this failed output", True)):
            with self.subTest(text=text):
                (self.fake / "transcript").write_text(text)
                if fails:
                    (self.fake / "fail-transcription").touch()
                self.command()
                target = Path(self.events("recording")[-1]["target"])
                self.command(expected=1 if fails else 0)
                self.assertFalse(target.exists())
                self.assertEqual(len(self.events("submitted")), 1)
                (self.fake / "fail-transcription").unlink(missing_ok=True)
        (self.fake / "transcript").write_text("Continue the previous request")
        self.command()
        self.command()
        last = self.events("request")[-1]
        self.assertEqual(last["text"], "Continue the previous request")
        self.assertEqual(last["session"], first["session"])
        for flag in (
            "--no-context-files",
            "--no-extensions",
            "--no-skills",
            "--no-prompt-templates",
        ):
            self.assertIn(flag, self.events("submitted")[-1]["args"])

    def test_failed_stop_cleans_recording_without_blocking_next_action(self):
        self.command()
        target = Path(self.events("recording")[0]["target"])
        (self.fake / "fail-stop").touch()
        self.command(expected=1)
        self.assertFalse(target.exists())
        self.assertEqual(self.events("submitted"), [])
        (self.fake / "fail-stop").unlink()
        self.command()
        self.command()
        self.assertEqual(len(self.events("request")), 1)

    def test_pi_failure_cleans_private_attachment_and_preserves_session(self):
        self.command()
        target = Path(self.events("recording")[0]["target"])
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(target.parent.parent.stat().st_mode & 0o777, 0o700)
        (self.fake / "fail-pi").touch()
        self.command(expected=1)
        self.assertFalse(target.exists())
        first_session = self.events("request")[0]["session"]
        self.assertEqual(Path(first_session).parent.stat().st_mode & 0o777, 0o700)
        (self.fake / "fail-pi").unlink()
        self.command()
        self.command()
        self.assertEqual(self.events("request")[1]["session"], first_session)

    def assert_submitted_request_survives_wrapper_termination(self, termination):
        self.command()
        target = Path(self.events("recording")[-1]["target"])
        self.hold("pi")
        worker = self.launch()
        self.ready("pi")
        os.kill(worker.pid, termination)  # Kill only the wrapper, not its child.
        worker.wait(timeout=5)
        self.command()
        self.assertEqual(len(self.events("recording")), 1)
        self.command()
        self.assertEqual(len(self.events("submitted")), 1)
        self.command("reset")
        self.command("cancel")
        self.assertTrue(target.exists(), "surviving Pi still needs its attachment")
        self.release("pi")
        self.ready("pi-completion")
        worker.communicate(timeout=5)
        # Completion makes the next command reconcile abandoned metadata.
        self.command()
        self.assertFalse(target.exists())
        self.command("cancel")
        self.assertEqual(self.events("request")[-1]["text"], "Open the browser")

    def test_sigkill_wrapper_preserves_submitted_request_and_busy_lifetime(self):
        self.assert_submitted_request_survives_wrapper_termination(signal.SIGKILL)

    def test_sigterm_wrapper_preserves_submitted_request_and_busy_lifetime(self):
        self.assert_submitted_request_survives_wrapper_termination(signal.SIGTERM)

    def test_rapid_reset_then_toggle_waits_for_daemon_cancellation(self):
        self.command()
        old_target = Path(self.events("recording")[0]["target"])
        self.hold("cancel")
        reset = self.launch("reset")
        self.ready("cancel")
        toggle = self.launch()
        self.release("cancel")
        self.finish(reset)
        self.finish(toggle)
        self.assertEqual(self.events("submitted"), [])
        self.assertFalse(old_target.exists())
        recordings = self.events("recording")
        self.assertEqual(len(recordings), 2)
        self.assertNotEqual(recordings[1]["target"], str(old_target))
        (self.fake / "transcript").write_text("Only the fresh request")
        self.command()
        self.assertEqual(self.events("request")[0]["text"], "Only the fresh request")


if __name__ == "__main__":
    unittest.main(verbosity=2)
