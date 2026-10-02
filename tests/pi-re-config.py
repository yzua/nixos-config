#!/usr/bin/env python3
"""Check independent RE initialization, controlled loading and secret-free doctor."""

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "home-manager/modules/ai/pi-re"
sys.path.insert(0, str(CODE))


def load(name):
    spec = importlib.util.spec_from_file_location(f"pi_re_{name}", CODE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


initializer = load("initialize")
launcher = load("launcher")


class ProfileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "coding"
        self.source.mkdir()
        self.agent = self.root / "re/agent"
        self.state = self.root / "state"
        self.source_values = {
            "settings.json": {
                "defaultProvider": "fixture",
                "defaultModel": "working-model",
                "extensions": ["unsafe.ts"],
                "skills": ["/unreviewed"],
                "sessionDir": "/foreign",
                "theme": "personal",
            },
            "models.json": {"providers": {"fixture": {"baseUrl": "https://fixture.invalid"}}},
            "auth.json": {"fixture": {"type": "api_key", "key": "CANARY-SECRET"}},
        }
        for name, value in self.source_values.items():
            (self.source / name).write_text(json.dumps(value))
        self.before = {p.name: p.read_bytes() for p in self.source.iterdir()}

    def initialize(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            initializer.initialize(self.agent, self.state, self.source)
        self.assertNotIn("CANARY-SECRET", output.getvalue())

    def test_independent_copy_without_coding_resources(self):
        self.initialize()
        settings = json.loads((self.agent / "settings.json").read_text())
        self.assertEqual(settings["defaultModel"], "working-model")
        for key in ("skills", "sessionDir", "theme"):
            self.assertNotIn(key, settings)
        self.assertEqual(settings["extensions"], ["-builtin:mcp"])
        self.assertEqual(
            json.loads((self.agent / "auth.json").read_text()), self.source_values["auth.json"]
        )
        self.assertEqual(self.before, {p.name: p.read_bytes() for p in self.source.iterdir()})
        for name in self.source_values:
            path = self.agent / name
            self.assertFalse(path.is_symlink())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_reinitialization_preserves_changed_auth_and_settings(self):
        self.initialize()
        auth = self.agent / "auth.json"
        auth.write_text('{"changed": true}')
        settings = self.agent / "settings.json"
        settings.write_text('{"defaultModel": "other"}')
        self.initialize()
        self.assertEqual(auth.read_text(), '{"changed": true}')
        self.assertEqual(settings.read_text(), '{"defaultModel": "other"}')

    def test_same_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            initializer.initialize(self.source, self.state, self.source)
        self.assertEqual(self.before, {p.name: p.read_bytes() for p in self.source.iterdir()})

    def test_destination_symlink_rejected(self):
        self.agent.mkdir(parents=True)
        (self.agent / "auth.json").symlink_to(self.source / "auth.json")
        with self.assertRaises(ValueError):
            initializer.initialize(self.agent, self.state, self.source)
        self.assertEqual(self.before, {p.name: p.read_bytes() for p in self.source.iterdir()})

    def test_overlapping_coding_directory_is_rejected(self):
        with self.assertRaises(ValueError):
            initializer.initialize(self.source / "nested", self.state, self.source)
        with self.assertRaises(ValueError):
            initializer.initialize(self.agent, self.source / "state", self.source)
        self.assertEqual(self.before, {p.name: p.read_bytes() for p in self.source.iterdir()})

    def test_ancestor_symlink_is_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            initializer.initialize(alias / "re/agent", self.state, self.source)
        self.assertFalse(self.agent.exists())

    def test_existing_hardlink_is_rejected_without_modifying_coding_file(self):
        self.agent.mkdir(parents=True)
        original = self.source / "auth.json"
        mode = original.stat().st_mode
        os.link(original, self.agent / "auth.json")
        with self.assertRaises(ValueError):
            initializer.initialize(self.agent, self.state, self.source)
        self.assertEqual(original.stat().st_mode, mode)
        self.assertEqual(self.before, {p.name: p.read_bytes() for p in self.source.iterdir()})

    def test_fifo_lock_is_rejected_without_blocking(self):
        self.state.mkdir()
        os.mkfifo(self.state / "initialize.lock")
        with self.assertRaises(ValueError):
            initializer.initialize(self.agent, self.state, self.source)

    def test_bad_source_is_rejected_without_copying_secret(self):
        (self.source / "models.json").write_text("[]")
        with self.assertRaises(ValueError):
            initializer.initialize(self.agent, self.state, self.source)
        self.assertFalse((self.agent / "auth.json").exists())
        self.assertFalse((self.agent / "settings.json").exists())

    def test_catalog_loading_is_explicit(self):
        resources = self.root / "resources"
        for skill in launcher.SKILLS:
            path = resources / "skills" / skill
            path.mkdir(parents=True)
            (path / "SKILL.md").write_text("fixture")
        extensions = [resources / name for name in ("flash-subagent.ts", "herdr.ts", "question.ts")]
        for extension in extensions:
            extension.write_text("export default function() {}")
        config = {
            "pi": "/fixture/bin/pi",
            "resources": str(resources),
            "herdrIntegration": str(extensions[1]),
            "questionExtension": str(extensions[2]),
        }
        locations = {"sessions": self.state / "sessions"}
        with patch.dict(os.environ, {"PI_RE_CHILD": "0"}):
            args = launcher.pi_arguments(config, locations, ["--print", "inspect"])
        self.assertEqual(
            [args[i + 1] for i, arg in enumerate(args) if arg == "--extension"],
            list(map(str, extensions)),
        )
        with patch.dict(os.environ, {"PI_RE_CHILD": "1"}):
            child = launcher.pi_arguments(config, locations, [])
        self.assertIn("--no-extensions", child)
        self.assertNotIn("--extension", child)
        for extension in extensions:
            extension.unlink()
            with (
                patch.dict(os.environ, {"PI_RE_CHILD": "0"}),
                self.assertRaisesRegex(ValueError, "root extension is missing"),
            ):
                launcher.pi_arguments(config, locations, [])
            extension.write_text("export default function() {}")
        for flag in ("--no-approve", "--no-context-files", "--no-extensions", "--no-skills"):
            self.assertIn(flag, args)
        self.assertEqual(args.count("--skill"), len(launcher.SKILLS))
        self.assertEqual(args[-2:], ["--print", "inspect"])
        self.assertIn(str(locations["sessions"]), args)

    def test_mapping_prompt_agrees_with_root_only_delegation(self):
        prompt = (CODE / "prompts/re-map.md").read_text()
        contract = (CODE / "contract.md").read_text()
        self.assertIn("MCP remains", prompt)
        self.assertIn("root-only delegation", prompt)
        self.assertIn("../contract.md#interfaces", prompt)
        self.assertNotIn("MCP/delegation remain disabled", prompt)
        self.assertIn("enabled root-only delegation", contract)
        resources = self.root / "resources"
        for skill in launcher.SKILLS:
            directory = resources / "skills" / skill
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text("fixture")
        extension = resources / "flash-subagent.ts"
        extension.write_text("fixture")
        reporter, question = resources / "herdr.ts", resources / "question.ts"
        for resource in (reporter, question):
            resource.write_text("fixture")
        config = {
            "pi": "/fixture/bin/pi",
            "resources": str(resources),
            "herdrIntegration": str(reporter),
            "questionExtension": str(question),
        }
        locations = {"sessions": self.state / "sessions"}
        with patch.dict(os.environ, {"PI_RE_CHILD": "0"}):
            self.assertIn(str(extension), launcher.pi_arguments(config, locations, []))
        with patch.dict(os.environ, {"PI_RE_CHILD": "1"}):
            self.assertNotIn(str(extension), launcher.pi_arguments(config, locations, []))

    def test_protected_flags_rejected(self):
        for flag in ("--approve", "--skill", "--extension", "--session-dir", "--system-prompt"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                launcher.checked_args([flag, "/foreign"], self.state)

    def test_foreign_session_rejected_and_re_session_accepted(self):
        self.state.mkdir()
        foreign = self.root / "foreign.jsonl"
        foreign.write_text("fixture")
        own = self.state / "own.jsonl"
        own.write_text("fixture")
        with self.assertRaises(ValueError):
            launcher.checked_args(["--session", str(foreign)], self.state)
        self.assertEqual(
            launcher.checked_args(["--session", str(own)], self.state),
            ["--session", str(own.resolve())],
        )

    def test_json_and_prompt_separator(self):
        self.assertEqual(
            launcher.checked_args(["--", "--approve"], self.state), ["--", "--approve"]
        )
        with self.assertRaises(ValueError):
            launcher.checked_args(["--mode", "rpc"], self.state)

    def test_doctor_has_no_subprocess_or_private_configuration_reads(self):
        config = {"capabilities": [{"id": "missing", "skill": "fixture", "tools": {}}]}
        with (
            patch("os.execv", side_effect=AssertionError),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            launcher.doctor(config, {"state": self.state}, True)
        result = json.loads(output.getvalue())
        self.assertTrue(result["rootRequired"])
        self.assertEqual(result["capabilities"][0]["availability"], "unavailable")
        self.assertNotIn("CANARY", output.getvalue())

    def test_paths_ignore_inherited_coding_profile(self):
        result = launcher.paths({"HOME": str(self.root), "PI_CODING_AGENT_DIR": "/coding"})
        self.assertEqual(result["agent"], self.root / ".local/share/pi-re/agent")
        with self.assertRaises(ValueError):
            launcher.paths({"HOME": str(self.root), "XDG_STATE_HOME": "relative"})


if __name__ == "__main__":
    unittest.main()
