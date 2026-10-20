#!/usr/bin/env python3
"""Offline Herdr/tmux RE resume routing; no models, real profiles or terminal commands."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / "home-manager/modules/ai/pi-base/resume-dispatch.py"


class ResumeRouting(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pi-resume-routing-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("real-pi", "pi-re", "pi-home", "pi-base"):
            executable = self.bin / name
            executable.write_text(
                f"#!{sys.executable}\nimport json,sys\nprint(json.dumps([sys.argv[0],sys.argv[1:]]))\n"
            )
            executable.chmod(0o755)
        self.state = self.root / "custom state"
        self.re = self.state / "pi-re/sessions"
        self.re.mkdir(parents=True)
        self.session = self.re / "session with ' quotes.jsonl"
        self.session.write_text("fixture")
        self.env = {
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "HOME": str(self.root),
            "XDG_STATE_HOME": str(self.state),
        }

    def run_dispatch(self, args, expected="real-pi", expected_args=None, cwd=None):
        process = subprocess.run(
            [sys.executable, str(DISPATCH), str(self.bin / "real-pi"), "--", *args],
            env=self.env,
            cwd=self.root if cwd is None else cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        executable, forwarded = json.loads(process.stdout)
        self.assertEqual(Path(executable).name, expected)
        self.assertEqual(forwarded, args if expected_args is None else expected_args)

    def test_herdr_exact_restore_and_tmux_manual_resume_preserve_re_profile(self):
        self.run_dispatch(["--session", str(self.session)], "pi-re")
        self.run_dispatch(["--model", "fixture", "--session", str(self.session)], "pi-re")

    def test_coding_p_alias_keeps_re_no_approve_without_stripping_values_or_prompts(self):
        self.run_dispatch(
            ["--approve", "--session", str(self.session)], "pi-re", ["--session", str(self.session)]
        )
        self.run_dispatch(
            ["-a", "--session", str(self.session), "--", "--approve"],
            "pi-re",
            ["--session", str(self.session), "--", "--approve"],
        )
        self.run_dispatch(["--model", "--approve", "--session", str(self.session)], "pi-re")

    def test_ordinary_pi_and_prompt_tokens_are_unchanged(self):
        for args in (
            [],
            ["--version"],
            ["--continue"],
            ["--session", str(self.root / "coding.jsonl")],
            ["--fork", str(self.root / "coding.jsonl")],
            ["auth", "check", "--session", str(self.session)],
            ["--export", str(self.session)],
            ["--", "--session", str(self.session)],
            ["--append-system-prompt", "--session", str(self.session)],
        ):
            self.run_dispatch(args)

    def test_native_session_ids_are_not_resolved_against_re_artifact_cwd(self):
        flash = self.state / "pi-re/subagents/jobs/fixture/sessions"
        flash.mkdir(parents=True)
        for cwd in (self.re, flash):
            for selector in ("--session", "--fork"):
                self.run_dispatch([selector, "coding-session-id"], cwd=cwd)

    def test_component_boundaries_are_not_string_prefixes(self):
        self.run_dispatch(["--session", str(self.state / "pi-re/sessions-other/test.jsonl")])

    def test_symlinks_and_missing_re_files_stay_with_guarded_re_launcher(self):
        link = self.root / "alias.jsonl"
        link.symlink_to(self.session)
        self.run_dispatch(["--session", str(link)], "pi-re")
        escape = self.re / "escaping.jsonl"
        escape.symlink_to(self.root / "outside.jsonl")
        self.run_dispatch(["--session", str(escape)], "pi-re")
        self.run_dispatch(["--session", str(self.re / "missing.jsonl")], "pi-re")

    def test_headless_flash_sessions_cannot_be_promoted_to_root_agents(self):
        for selector in ("--session", "--fork"):
            args = [selector, str(self.state / "pi-re/subagents/jobs/fixture/sessions/child.jsonl")]
            process = subprocess.run(
                [sys.executable, str(DISPATCH), str(self.bin / "real-pi"), "--", *args],
                env=self.env,
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("not interactive root sessions", process.stderr)
            self.assertEqual(process.stdout, "")

    def test_interactive_workers_require_saved_loadout_replay(self):
        for profile in ("pi-base", "pi-home", "pi-re"):
            artifact = self.state / profile / "interactive-subagents/sessions/cwd/worker.jsonl"
            for selector in ("--session", "--fork"):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(DISPATCH),
                        str(self.bin / "real-pi"),
                        "--",
                        selector,
                        str(artifact),
                    ],
                    env=self.env,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("saved loadout", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_personal_and_base_sessions_route_to_their_owner(self):
        for profile in ("pi-home", "pi-base"):
            session = self.state / profile / "sessions/root.jsonl"
            self.run_dispatch(["--session", str(session)], profile)
            self.run_dispatch(
                ["--approve", "--session", str(session)], profile, ["--session", str(session)]
            )

    def test_research_artifacts_and_their_aliases_are_not_root_sessions(self):
        artifact = self.state / "pi-re/research/parents/root/jobs/worker/native.jsonl"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("fixture")
        alias = self.root / "research-alias.jsonl"
        alias.symlink_to(artifact)
        for file in (artifact, alias):
            result = subprocess.run(
                [
                    sys.executable,
                    str(DISPATCH),
                    str(self.bin / "real-pi"),
                    "--",
                    "--session",
                    str(file),
                ],
                env=self.env,
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not interactive root sessions", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_default_state_location_comes_from_caller_home(self):
        del self.env["XDG_STATE_HOME"]
        self.run_dispatch(
            ["--session", str(self.root / ".local/state/pi-re/sessions/test.jsonl")], "pi-re"
        )


if __name__ == "__main__":
    unittest.main()
