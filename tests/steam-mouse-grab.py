"""Offline regression tests for Proton fullscreen mouse capture defaults."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "home-manager/modules/steam-mouse-grab.py"
spec = importlib.util.spec_from_file_location("steam_mouse_grab", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MouseGrabTests(unittest.TestCase):
    def test_add_and_repeat(self):
        original = 'WINE REGISTRY Version 2\n\n[Other]\n"keep"="yes"\n'
        changed = module.enable_grab(original)
        self.assertIn(original.rstrip(), changed)
        self.assertIn(module.SECTION + "\n" + module.VALUE, changed)
        self.assertEqual(changed, module.enable_grab(changed))

    def test_replace_only_grab_value(self):
        original = (
            module.SECTION + ' 123\n#time=abc\n"GrabFullscreen"="N"\n'
            '"Other"="keep"\n\n[Next]\n"GrabFullscreen"="N"\n'
        )
        changed = module.enable_grab(original)
        self.assertEqual(changed.count(module.VALUE), 1)
        self.assertIn('[Next]\n"GrabFullscreen"="N"', changed)
        self.assertIn('"Other"="keep"', changed)
        self.assertIn("#time=abc", changed)

    def test_existing_section_without_value(self):
        changed = module.enable_grab(module.SECTION + '\n"Other"="keep"\n\n[Next]\n')
        self.assertEqual(changed.count(module.SECTION), 1)
        self.assertIn(module.VALUE, changed)

    def test_backup_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "user.reg"
            original = "WINE REGISTRY Version 2\n"
            path.write_text(original)
            path.chmod(0o640)
            with patch.object(module, "wine_running", return_value=False):
                self.assertTrue(module.apply_registry(path))
                self.assertFalse(module.apply_registry(path))
            self.assertEqual(path.with_name("user.reg.before-mouse-grab").read_text(), original)
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    def test_abort_if_wine_starts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "user.reg"
            original = "WINE REGISTRY Version 2\n"
            path.write_text(original)
            with patch.object(module, "wine_running", return_value=True):
                with self.assertRaises(ValueError):
                    module.apply_registry(path)
            self.assertEqual(path.read_text(), original)

    def test_proc_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            (proc / "42").mkdir()
            (proc / "42/comm").write_text("wineserver\n")
            self.assertTrue(module.wine_running(proc))
            (proc / "42/comm").write_text("steam\n")
            self.assertFalse(module.wine_running(proc))

    def test_process_exit_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            (proc / "42").mkdir()
            with patch.object(Path, "read_text", side_effect=ProcessLookupError):
                self.assertFalse(module.wine_running(proc))

    def test_extra_roots_preserve_defaults(self):
        with (
            patch("sys.argv", ["steam-mouse-grab", "--steam-root", "/extra"]),
            patch.object(module, "wine_running", return_value=False),
            patch.object(module, "steam_libraries", return_value=[]) as libraries,
            patch("builtins.print"),
        ):
            module.main()
        roots = libraries.call_args.args[0]
        self.assertIn(Path.home() / ".local/share/Steam", roots)
        self.assertIn(Path("/extra"), roots)

    def test_library_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Steam"
            other = Path(tmp) / "Library with spaces"
            (root / "steamapps").mkdir(parents=True)
            (root / "steamapps/libraryfolders.vdf").write_text(
                f'"libraryfolders" {{ "1" {{ "path" "{other}" }} }}'
            )
            self.assertEqual(set(module.steam_libraries([root, root])), {root, other})


if __name__ == "__main__":
    unittest.main()
