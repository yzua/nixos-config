#!/usr/bin/env python3
"""Check shared-config migration, controlled RE loading and secret-free doctor."""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
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

    def test_shared_configuration_is_not_copied_or_rewritten(self):
        self.initialize()
        self.assertEqual(self.before, {p.name: p.read_bytes() for p in self.source.iterdir()})
        self.assertFalse(any(self.agent.iterdir()))
        marker = json.loads((self.state / "shared-config-v1.json").read_text())
        self.assertEqual(marker["credentialMode"], "shared")
        self.assertEqual(marker["agentDir"], str(self.source))

    def test_unrecognized_legacy_values_are_archived_once_without_merging(self):
        self.agent.mkdir(parents=True)
        for name in self.source_values:
            (self.agent / name).write_text('{"legacy": true}')
        self.initialize()
        archive = self.agent.parent / "backups/shared-config-v1"
        before = {p.name: p.read_bytes() for p in archive.iterdir()}
        self.assertEqual(set(before), set(self.source_values))
        for path in archive.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        (self.source / "auth.json").write_text('{"changed": true}')
        (self.source / "settings.json").write_text('{"defaultModel": "other"}')
        self.initialize()
        self.assertEqual((self.source / "auth.json").read_text(), '{"changed": true}')
        self.assertEqual((self.source / "settings.json").read_text(), '{"defaultModel": "other"}')
        self.assertEqual(before, {p.name: p.read_bytes() for p in archive.iterdir()})
        self.assertFalse(any(self.agent.iterdir()))

    def test_missing_compatible_providers_models_and_logins_are_merged(self):
        self.agent.mkdir(parents=True)
        legacy = {
            "settings.json": {
                "defaultProvider": "rea-only",
                "defaultModel": "not-the-current-default",
            },
            "models.json": {
                "providers": {
                    "fixture": {
                        "baseUrl": "https://fixture.invalid",
                        "models": [{"id": "extra-model"}],
                    },
                    "rea-only": {
                        "baseUrl": "https://rea-only.invalid",
                        "models": [{"id": "flash"}],
                    },
                }
            },
            "auth.json": {
                "fixture": {"type": "api_key", "key": "DO-NOT-OVERWRITE-LIVE"},
                "rea-only": {"type": "api_key", "key": "SYNTHETIC-RE-ONLY"},
                "oauth-only": {
                    "type": "oauth",
                    "access": "SYNTHETIC-ACCESS",
                    "refresh": "SYNTHETIC-REFRESH",
                    "expires": 1,
                },
            },
        }
        for name, value in legacy.items():
            (self.agent / name).write_text(json.dumps(value))
        self.initialize()
        self.assertEqual((self.source / "settings.json").read_bytes(), self.before["settings.json"])
        models = json.loads((self.source / "models.json").read_text())["providers"]
        self.assertEqual(models["fixture"]["models"], [{"id": "extra-model"}])
        self.assertEqual(models["rea-only"], legacy["models.json"]["providers"]["rea-only"])
        auth = json.loads((self.source / "auth.json").read_text())
        self.assertEqual(auth["fixture"], self.source_values["auth.json"]["fixture"])
        self.assertEqual(auth["rea-only"], legacy["auth.json"]["rea-only"])
        self.assertEqual(auth["oauth-only"], legacy["auth.json"]["oauth-only"])
        self.assertEqual((self.source / "auth.json").stat().st_mode & 0o777, 0o600)
        for name, value in legacy.items():
            self.assertEqual(
                json.loads((self.agent.parent / "backups/shared-config-v1" / name).read_text()),
                value,
            )
        after = {p.name: p.read_bytes() for p in self.source.iterdir()}
        self.initialize()
        self.assertEqual(after, {p.name: p.read_bytes() for p in self.source.iterdir()})

    def test_merge_recovers_if_interrupted_between_model_and_auth_writes(self):
        self.agent.mkdir(parents=True)
        (self.agent / "models.json").write_text(
            json.dumps({"providers": {"rea-only": {"baseUrl": "https://rea-only.invalid"}}})
        )
        (self.agent / "auth.json").write_text(
            json.dumps({"rea-only": {"type": "api_key", "key": "SYNTHETIC-RE"}})
        )
        original = initializer.write_private

        def interrupt(path, value):
            if path == self.source / "auth.json":
                raise OSError("fixture interruption")
            original(path, value)

        with (
            patch.object(initializer, "write_private", side_effect=interrupt),
            self.assertRaises(OSError),
        ):
            self.initialize()
        self.assertIn(
            "rea-only", json.loads((self.source / "models.json").read_text())["providers"]
        )
        self.assertNotIn("rea-only", json.loads((self.source / "auth.json").read_text()))
        self.assertFalse((self.state / "shared-config-v1.json").exists())
        self.initialize()
        self.assertIn("rea-only", json.loads((self.source / "auth.json").read_text()))
        self.assertEqual((self.source / "settings.json").read_bytes(), self.before["settings.json"])

    def test_busy_shared_native_mutex_prevents_merge_without_removing_foreign_lock(self):
        mutex = self.source / "auth.json.lock"
        mutex.mkdir()
        with self.assertRaisesRegex(ValueError, "busy"):
            self.initialize()
        self.assertTrue(mutex.is_dir())
        self.assertEqual((self.source / "auth.json").read_bytes(), self.before["auth.json"])
        self.assertFalse((self.state / "shared-config-v1.json").exists())
        mutex.rmdir()
        self.initialize()

    def test_conflicting_endpoints_and_implicit_current_providers_keep_live_routing_and_auth(self):
        models = {"providers": {"custom": {"baseUrl": "https://current.invalid"}}}
        auth = {"implicit": {"type": "api_key", "key": "LIVE-IMPLICIT"}}
        legacy_models = {
            "providers": {
                "custom": {"baseUrl": "https://old.invalid", "models": [{"id": "old"}]},
                "implicit": {"baseUrl": "https://old.invalid"},
                "selected": {"baseUrl": "https://old.invalid"},
            }
        }
        legacy_auth = {
            name: {"type": "api_key", "key": "DO-NOT-IMPORT"}
            for name in ("custom", "implicit", "selected")
        }
        merged_models, merged_auth, _counts = initializer.compatible_additions(
            models, auth, legacy_models, legacy_auth, "selected"
        )
        self.assertEqual(merged_models, models)
        self.assertEqual(merged_auth, auth)
        # An old built-in login must not be sent to a current custom endpoint either.
        merged_models, merged_auth, _counts = initializer.compatible_additions(
            models, auth, {}, legacy_auth, None
        )
        self.assertNotIn("custom", merged_auth)
        self.assertEqual(merged_models, models)

    def test_interrupted_archive_can_resume_without_losing_legacy_files(self):
        self.agent.mkdir(parents=True)
        for name in self.source_values:
            (self.agent / name).write_text('{"legacy": true}')
        original = os.rename

        def interrupt(path, destination):
            if path == self.agent / "models.json":
                raise OSError("fixture interruption")
            return original(path, destination)

        with patch("os.rename", interrupt), self.assertRaises(OSError):
            self.initialize()
        self.assertFalse((self.state / "shared-config-v1.json").exists())
        self.initialize()
        self.assertFalse(any(self.agent.iterdir()))
        self.assertEqual(len(list((self.agent.parent / "backups/shared-config-v1").iterdir())), 3)

    def test_atomic_archive_preserves_updates_through_an_open_legacy_descriptor(self):
        self.agent.mkdir(parents=True)
        auth = self.agent / "auth.json"
        auth.write_text('{"old": true}')
        with auth.open("r+") as writer:
            self.initialize()
            writer.seek(0)
            writer.write('{"new": true}')
            writer.truncate()
            writer.flush()
        archive = self.agent.parent / "backups/shared-config-v1/auth.json"
        self.assertEqual(json.loads(archive.read_text()), {"new": True})
        self.assertFalse(auth.exists())

    def test_legacy_native_locks_and_live_session_guard_preserve_files(self):
        self.agent.mkdir(parents=True)
        auth = self.agent / "auth.json"
        auth.write_text('{"legacy": true}')
        mutex = self.agent / "auth.json.lock"
        mutex.mkdir()
        with self.assertRaisesRegex(ValueError, "busy"):
            self.initialize()
        self.assertTrue(mutex.is_dir())
        self.assertTrue(auth.exists())
        mutex.rmdir()
        with patch.object(initializer, "legacy_process_running", return_value=True):
            with self.assertRaisesRegex(ValueError, "Close all legacy"):
                self.initialize()
        self.assertTrue(auth.exists())
        self.assertFalse(any(self.agent.glob("*.lock")))

    def test_abrupt_exit_after_archive_rename_recovers_only_stale_native_mutexes(self):
        self.agent.mkdir(parents=True)
        originals = {}
        for name in initializer.FILES:
            originals[name] = b'{"legacy": true}'
            (self.agent / name).write_bytes(originals[name])
        script = f"""
import importlib.util, os
from pathlib import Path
spec = importlib.util.spec_from_file_location("migration", {str(CODE / "initialize.py")!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
rename = os.rename
def crash(source, destination):
    rename(source, destination)
    os._exit(77)
os.rename = crash
module.initialize(Path({str(self.agent)!r}), Path({str(self.state)!r}), Path({str(self.source)!r}))
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", script], capture_output=True, timeout=10
        )
        self.assertEqual(result.returncode, 77, result.stderr)
        self.assertEqual(len(list(self.agent.glob("*.lock"))), 3)
        with self.assertRaisesRegex(ValueError, "busy"):
            self.initialize()
        for mutex in self.agent.glob("*.lock"):
            stale = mutex.stat().st_mtime - 31
            os.utime(mutex, (stale, stale))
        self.initialize()
        self.assertFalse(any(self.agent.iterdir()))
        backup = self.agent.parent / "backups/shared-config-v1"
        self.assertEqual({p.name: p.read_bytes() for p in backup.iterdir()}, originals)

    def test_live_writer_and_nonempty_or_foreign_mutexes_are_never_removed(self):
        self.agent.mkdir(parents=True)
        mutex = self.agent / "settings.json.lock"
        mutex.mkdir()
        stale = mutex.stat().st_mtime - 31
        os.utime(mutex, (stale, stale))
        identity = initializer.mutex_identity(mutex)
        with patch.object(initializer, "legacy_process_running", return_value=True):
            with self.assertRaisesRegex(ValueError, "busy"):
                self.initialize()
        self.assertEqual(initializer.mutex_identity(mutex), identity)
        (mutex / "foreign").write_text("preserve")
        with self.assertRaisesRegex(ValueError, "unsafe or nonempty"):
            self.initialize()
        self.assertEqual((mutex / "foreign").read_text(), "preserve")
        (mutex / "foreign").unlink()
        mutex.rmdir()
        mutex.symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "unsafe or nonempty"):
            self.initialize()
        self.assertTrue(mutex.is_symlink())

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
        extensions = [
            resources / name
            for name in (
                "flash-subagent.ts",
                "research-subagent.ts",
                "herdr.ts",
                "question.ts",
                "search.ts",
                "fetch.ts",
            )
        ]
        for extension in extensions:
            extension.write_text("export default function() {}")
        config = {
            "pi": "/fixture/bin/pi",
            "resources": str(resources),
            "commonExtensions": list(map(str, extensions[2:])),
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
        self.assertIn("REA MCP is", prompt)
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
        (resources / "research-subagent.ts").write_text("fixture")
        reporter, question = resources / "herdr.ts", resources / "question.ts"
        search, fetch = resources / "search.ts", resources / "fetch.ts"
        for resource in (reporter, question, search, fetch):
            resource.write_text("fixture")
        config = {
            "pi": "/fixture/bin/pi",
            "resources": str(resources),
            "commonExtensions": list(map(str, (reporter, question, search, fetch))),
        }
        locations = {"sessions": self.state / "sessions"}
        with patch.dict(os.environ, {"PI_RE_CHILD": "0"}):
            self.assertIn(str(extension), launcher.pi_arguments(config, locations, []))
        with patch.dict(os.environ, {"PI_RE_CHILD": "1"}):
            self.assertNotIn(str(extension), launcher.pi_arguments(config, locations, []))

    def test_managed_mcp_is_session_only_and_preserves_foreign_config(self):
        config = {"reaSkill": "/pinned/skill"}
        locations = {"legacy_agent": self.agent}
        with patch.dict(os.environ, {"PI_RE_CHILD": "0"}):
            launcher.validate_rea_mcp(config, locations)
            self.assertFalse((self.agent / "mcp.json").exists())
            self.agent.mkdir(parents=True)
            path = self.agent / "mcp.json"
            for name in ("foreign", "rea"):
                path.write_text(json.dumps({"mcpServers": {name: {"command": "evil"}}}))
                before = path.read_bytes()
                with self.assertRaisesRegex(ValueError, "Foreign"):
                    launcher.validate_rea_mcp(config, locations)
                self.assertEqual(path.read_bytes(), before)
            path.write_text('{"mcpServers":{},"autoEnableCodemode":false}')
            launcher.validate_rea_mcp(config, locations)
            self.assertIn("false", path.read_text())
            path.unlink()
            target = self.root / "foreign-mcp.json"
            target.write_text("{}")
            path.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlinks"):
                launcher.validate_rea_mcp(config, locations)
            self.assertEqual(target.read_text(), "{}")
        with patch.dict(os.environ, {"PI_RE_CHILD": "1"}):
            launcher.validate_rea_mcp(config, locations)

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
        self.assertEqual(result["agent"], self.root / ".pi/agent")
        self.assertEqual(result["legacy_agent"], self.root / ".local/share/pi-re/agent")
        with self.assertRaises(ValueError):
            launcher.paths({"HOME": str(self.root), "XDG_STATE_HOME": "relative"})


if __name__ == "__main__":
    unittest.main()
