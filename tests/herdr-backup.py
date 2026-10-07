#!/usr/bin/env python3
"""Exercise private Herdr recovery copies without touching a live server."""

import copy
import fcntl
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "home-manager/modules/ai/herdr-backup.py"
spec = importlib.util.spec_from_file_location("herdr_backup", SOURCE)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class LayoutBackup(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="herdr-backup-test-")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.config = root / "config"
        self.state = root / "state"
        self.config.mkdir()
        self.now = datetime(2026, 1, 1, tzinfo=UTC)
        # Synthetic portable layout follows Herdr v0.9.3's SessionSnapshot schema:
        # https://github.com/herdrdev/herdr/blob/v0.9.3/src/persist/snapshot.rs
        self.layout = {
            "version": 3,
            "active": 0,
            "selected": 0,
            "workspaces": [
                {
                    "identity_cwd": str(root / "workspace"),
                    "tabs": [
                        {
                            "layout": {"Pane": 1},
                            "zoomed": False,
                            "focused": 1,
                            "root_pane": 1,
                            "panes": {
                                "1": {
                                    "cwd": str(root / "workspace"),
                                    "agent_session": {
                                        "source": "herdr:pi",
                                        "agent": "pi",
                                        "kind": "path",
                                        "value": str(root / "chat.jsonl"),
                                    },
                                }
                            },
                        }
                    ],
                }
            ],
        }

    def save(self, layout=None, path=None):
        path = path or self.config / "session.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.layout if layout is None else layout))

    def run_backup(self, now=None):
        return backup.backup_layouts(self.config, self.state, now or self.now)

    def test_exact_private_copy_and_idempotency(self):
        self.save()
        self.assertEqual(self.run_backup(), 1)
        self.assertEqual(self.run_backup(self.now + timedelta(minutes=5)), 0)
        saved = self.state / "default/latest.json"
        self.assertEqual(json.loads(saved.read_text()), self.layout)
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        self.assertEqual(saved.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertEqual(len(list(saved.parent.glob("snapshot-*.json"))), 1)

    def test_deleted_corrupt_and_empty_state_cannot_destroy_last_good_copy(self):
        self.save()
        self.run_backup()
        saved = (self.state / "default/latest.json").read_bytes()
        for value in ("", "{", '{"version":3,"workspaces":[]}', '{"version":3,"workspaces":[{}]}'):
            with self.subTest(value=value):
                (self.config / "session.json").write_text(value)
                self.assertEqual(self.run_backup(), 0)
                self.assertEqual((self.state / "default/latest.json").read_bytes(), saved)
        (self.config / "session.json").unlink()
        self.assertEqual(self.run_backup(), 0)
        self.assertEqual((self.state / "default/latest.json").read_bytes(), saved)

    def test_disappearing_source_does_not_skip_other_sessions(self):
        self.save()
        self.save(path=self.config / "sessions/review/session.json")
        original_open = backup.os.open
        live = self.config / "session.json"

        def disappearing_open(path, *args, **kwargs):
            if Path(path) == live:
                raise FileNotFoundError(2, "fixture concurrent removal")
            return original_open(path, *args, **kwargs)

        with patch.object(backup.os, "open", disappearing_open):
            self.assertEqual(self.run_backup(), 1)
        self.assertTrue((self.state / "named-review/latest.json").exists())

    def test_named_sessions_are_separate_and_unrelated_json_is_ignored(self):
        self.save()
        self.save(path=self.config / "sessions/review/session.json")
        self.save(path=self.config / "plugins/fixture/session.json")
        self.assertEqual(self.run_backup(), 2)
        self.assertTrue((self.state / "named-review/latest.json").exists())
        self.assertFalse((self.state / "plugins").exists())

    def test_rotation_preserves_daily_recovery_beyond_recent_changes(self):
        for index in range(110):
            self.layout["selected"] = index
            self.save()
            self.run_backup(self.now + timedelta(minutes=index * 5))
        folder = self.state / "default"
        self.assertEqual(len(list(folder.glob("snapshot-*.json"))), 96)
        self.assertEqual(len(list(folder.glob("day-*.json"))), 1)
        self.assertEqual(json.loads((folder / "latest.json").read_text())["selected"], 109)
        for index in range(1, 10):
            self.layout["selected"] = index + 110
            self.save()
            self.run_backup(self.now + timedelta(days=index))
        self.assertEqual(len(list(folder.glob("day-*.json"))), 8)

    def test_stale_running_server_warns_without_stopping_it(self):
        with (
            patch.object(backup.subprocess, "check_output", return_value="herdr 0.9.3\n"),
            patch.object(backup.subprocess, "run") as status,
            patch("builtins.print") as output,
        ):
            status.return_value.returncode = 0
            status.return_value.stdout = "status: running\nversion: 0.9.1\n"
            backup.check_server("/fixture/herdr")
            status.assert_called_once_with(
                ["/fixture/herdr", "status", "server"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertIn("has not adopted", output.call_args.args[0])
            output.reset_mock()
            status.return_value.stdout = "status: running\nversion: 0.9.3\n"
            backup.check_server("/fixture/herdr")
            output.assert_not_called()

    def test_malformed_panes_and_layout_never_replace_good_history(self):
        self.save()
        self.run_backup()
        folder = self.state / "default"
        before = {path.name: path.read_bytes() for path in folder.iterdir()}
        for field, value in (
            ("layout", None),
            ("panes", [None]),
            ("panes", {"1": None}),
            ("panes", {"1": {}}),
            ("zoomed", "false"),
            ("layout", {"Pane": 2}),
            (
                "layout",
                {
                    "Split": {
                        "direction": "Diagonal",
                        "ratio": 0.5,
                        "first": {"Pane": 1},
                        "second": {"Pane": 1},
                    }
                },
            ),
        ):
            with self.subTest(field=field, value=value):
                layout = copy.deepcopy(self.layout)
                tab = layout["workspaces"][0]["tabs"][0]
                if value is None:
                    del tab[field]
                else:
                    tab[field] = value
                self.save(layout)
                self.assertEqual(self.run_backup(self.now + timedelta(minutes=5)), 0)
                self.assertEqual(
                    {path.name: path.read_bytes() for path in folder.iterdir()}, before
                )

    def test_recognized_metadata_types_cannot_replace_good_history(self):
        self.save()
        self.run_backup()
        folder = self.state / "default"
        before = {path.name: path.read_bytes() for path in folder.iterdir()}
        for scope, field, value in (
            ("session", "selected", "corrupt"),
            ("session", "active", False),
            ("session", "sidebar_width", -1),
            ("session", "sidebar_section_split", "bad"),
            ("session", "collapsed_space_keys", [None]),
            ("workspace", "id", 1),
            ("workspace", "custom_name", []),
            ("workspace", "public_pane_numbers", {"bad": 2}),
            ("workspace", "public_tab_numbers", [False]),
            ("workspace", "next_public_pane_number", None),
            ("workspace", "next_public_tab_number", -1),
            ("workspace", "worktree_space", {}),
            ("tab", "custom_name", {}),
            ("tab", "root_pane", "1"),
            ("pane", "label", {}),
            ("pane", "agent_session", {"kind": "path", "value": "x"}),
            ("pane", "launch_argv", [1]),
        ):
            with self.subTest(scope=scope, field=field):
                layout = copy.deepcopy(self.layout)
                workspace = layout["workspaces"][0]
                tab = workspace["tabs"][0]
                owner = {
                    "session": layout,
                    "workspace": workspace,
                    "tab": tab,
                    "pane": tab["panes"]["1"],
                }[scope]
                owner[field] = value
                self.save(layout)
                self.assertEqual(self.run_backup(self.now + timedelta(minutes=5)), 0)
                self.assertEqual(
                    {path.name: path.read_bytes() for path in folder.iterdir()}, before
                )

    def test_non_json_strings_and_numbers_leave_history_unchanged(self):
        self.save()
        self.run_backup()
        folder = self.state / "default"
        before = {path.name: path.read_bytes() for path in folder.iterdir()}
        for field, value in (
            ("unknown", "\ud800"),
            ("\ud800", "value"),
            ("unknown", ["\udfff"]),
            ("unknown", float("inf")),
        ):
            with self.subTest(field=repr(field), value=repr(value)):
                layout = copy.deepcopy(self.layout)
                layout[field] = value
                self.save(layout)
                self.assertEqual(self.run_backup(), 0)
                self.assertEqual(
                    {path.name: path.read_bytes() for path in folder.iterdir()}, before
                )

    def test_supported_split_tree_and_unknown_versions(self):
        layout = copy.deepcopy(self.layout)
        tab = layout["workspaces"][0]["tabs"][0]
        tab["panes"]["2"] = {"cwd": self.layout["workspaces"][0]["identity_cwd"]}
        tab["layout"] = {
            "Split": {
                "direction": "Horizontal",
                "ratio": 0.6,
                "first": {"Pane": 1},
                "second": {"Pane": 2},
            }
        }
        self.save(layout)
        self.assertEqual(self.run_backup(), 1)
        saved = (self.state / "default/latest.json").read_bytes()
        for version in (None, True, 2, 999):
            with self.subTest(version=version):
                layout["version"] = version
                self.save(layout)
                self.assertEqual(self.run_backup(), 0)
                self.assertEqual((self.state / "default/latest.json").read_bytes(), saved)

    def test_busy_lock_fails_promptly(self):
        self.save()
        self.state.mkdir()
        with (self.state / ".lock").open("wb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.run_backup()
        self.assertFalse((self.state / "default").exists())

    def test_untrusted_recovery_aliases_are_replaced_not_followed(self):
        self.save()
        self.run_backup()
        folder = self.state / "default"
        for filename in ("latest.json", "day-2026-01-01.json"):
            with self.subTest(filename=filename):
                path = folder / filename
                alias = self.config / filename
                os.link(path, alias)
                alias.chmod(0o644)
                self.assertEqual(self.run_backup(), 0)
                self.assertEqual(path.stat().st_nlink, 1)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertNotEqual(path.stat().st_ino, alias.stat().st_ino)
                alias.unlink()
                path.unlink()
                path.symlink_to(self.config / "session.json")
                before = (self.config / "session.json").read_bytes()
                with self.assertRaisesRegex(ValueError, "regular files"):
                    self.run_backup()
                self.assertEqual((self.config / "session.json").read_bytes(), before)
                path.unlink()
                self.run_backup()

    def test_historical_aliases_repaired_without_rewriting_history(self):
        self.save()
        self.run_backup()
        folder = self.state / "default"
        original = (folder / "latest.json").read_bytes()
        paths = [next(folder.glob("snapshot-*.json")), folder / "day-2026-01-01.json"]
        for path in paths:
            os.link(path, self.config / path.name)
            path.chmod(0o644)
        self.layout["workspaces"][0]["tabs"][0]["panes"]["1"]["label"] = "new layout"
        self.save()
        self.run_backup(self.now + timedelta(days=1))
        for path in paths:
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(path.stat().st_nlink, 1)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotEqual(path.stat().st_ino, (self.config / path.name).stat().st_ino)

    def test_recovery_only_state_is_private_after_live_layout_loss(self):
        self.save()
        named = self.config / "sessions/review/session.json"
        self.save(path=named)
        self.run_backup()
        histories = []
        for folder in (self.state / "default", self.state / "named-review"):
            for path in folder.iterdir():
                alias = self.config / (folder.name + "-" + path.name)
                os.link(path, alias)
                path.chmod(0o644)
                histories.append((path, path.read_bytes()))
        (self.config / "session.json").write_text("corrupt")
        named.unlink()
        named.parent.rmdir()
        self.assertEqual(self.run_backup(), 0)
        for path, original in histories:
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(path.stat().st_nlink, 1)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_data_growth_after_open_is_bounded_and_rejected(self):
        source = self.config / "session.json"
        source.write_bytes(b"{}")
        original_fstat = backup.os.fstat
        first = True

        def growing_fstat(descriptor):
            nonlocal first
            info = original_fstat(descriptor)
            if first:
                first = False
                source.write_bytes(b"x" * 1025)
            return info

        with (
            patch.object(backup.os, "fstat", growing_fstat),
            patch.object(backup, "MAX_LAYOUT_BYTES", 1024),
        ):
            self.assertEqual(backup.read_regular(source), (None, False))

    def test_source_replacement_is_not_followed_or_blocking(self):
        source = self.config / "session.json"
        foreign = self.config / "foreign.json"
        self.save(path=foreign)
        self.save()
        original_open = backup.os.open
        for kind in ("symlink", "fifo", "oversize"):
            with self.subTest(kind=kind):
                source.unlink(missing_ok=True)
                self.save()
                replaced = False

                def racing_open(path, flags, *args, **kwargs):
                    nonlocal replaced
                    if Path(path) == source and not replaced:
                        replaced = True
                        source.unlink()
                        if kind == "symlink":
                            source.symlink_to(foreign)
                        elif kind == "fifo":
                            os.mkfifo(source)
                        else:
                            source.write_bytes(b"x" * 1025)
                    return original_open(path, flags, *args, **kwargs)

                with (
                    patch.object(backup.os, "open", racing_open),
                    patch.object(backup, "MAX_LAYOUT_BYTES", 1024, create=True),
                ):
                    self.assertEqual(self.run_backup(), 0)
                self.assertTrue(replaced, "Source must be opened through verified descriptor")
                self.assertFalse((self.state / "default/latest.json").exists())

    def test_lock_symlink_fifo_and_hardlink_fail_without_blocking_or_mutation(self):
        self.save()
        self.state.mkdir()
        victim = self.config / "victim"
        victim.write_text("untouched")
        before = victim.stat().st_mode
        lock = self.state / ".lock"
        for kind in ("symlink", "fifo", "hardlink"):
            with self.subTest(kind=kind):
                if kind == "symlink":
                    lock.symlink_to(victim)
                elif kind == "fifo":
                    os.mkfifo(lock)
                else:
                    os.link(victim, lock)
                with self.assertRaises((ValueError, OSError)):
                    self.run_backup()
                lock.unlink()
                self.assertEqual(victim.read_text(), "untouched")
                self.assertEqual(victim.stat().st_mode, before)

    def test_state_ancestor_symlink_rejected_before_creating_directories(self):
        alias = self.config / "alias"
        alias.symlink_to(self.config, target_is_directory=True)
        with self.assertRaises(ValueError):
            backup.backup_layouts(self.config, alias / "nested/recovery", self.now)
        self.assertFalse((self.config / "nested").exists())

    def test_activation_guard_warns_while_timer_reports_failure(self):
        module = SOURCE.with_suffix(".nix").read_text()
        self.assertIn("if ! run", module)
        self.assertIn("WARNING:", module)
        self.assertIn("TimeoutStartSec", module)
        with (
            patch.object(
                backup.subprocess,
                "check_output",
                side_effect=subprocess.TimeoutExpired("fixture", 10),
            ),
            patch("builtins.print") as output,
        ):
            backup.check_server("/fixture/herdr")
            self.assertIn("WARNING:", output.call_args.args[0])

    def test_live_layout_is_not_modified(self):
        self.save()
        live = self.config / "session.json"
        before = (live.read_bytes(), live.stat().st_mtime_ns, live.stat().st_mode)
        self.run_backup()
        self.assertEqual((live.read_bytes(), live.stat().st_mtime_ns, live.stat().st_mode), before)


if __name__ == "__main__":
    unittest.main()
