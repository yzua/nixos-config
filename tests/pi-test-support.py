#!/usr/bin/env python3
"""Regress shared offline resources/isolation without any installed Pi dependency."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_test_support import isolated_environment, require_pi, require_web_fetch_dependencies

TESTS = Path(__file__).resolve().parent


class OfflineSupport(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pi-support-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.executable = self.root / "pi"
        self.executable.write_text("#!/bin/sh\nexit 0\n")
        self.executable.chmod(0o755)
        self.dependencies = self.root / "web-fetch"
        (self.dependencies / "node_modules").mkdir(parents=True)

    def test_pi_override_is_validated_and_works_after_fixture_cwd_changes(self):
        with patch.dict(os.environ, {"PI_BIN": str(self.executable), "PATH": ""}, clear=True):
            executable = require_pi()
        result = subprocess.run([executable], cwd=self.dependencies, capture_output=True)
        self.assertEqual(result.returncode, 0)
        for invalid in [self.root / "missing", self.dependencies, self.executable]:
            with self.subTest(invalid=invalid):
                self.executable.chmod(0o644)
                with patch.dict(os.environ, {"PI_BIN": str(invalid)}, clear=True):
                    with self.assertRaises(SystemExit) as error:
                        require_pi()
                self.assertEqual(str(error.exception), f"PI_BIN is not executable: {invalid}")

    def test_pi_path_fallback_and_empty_override(self):
        for override in [{}, {"PI_BIN": ""}]:
            with self.subTest(override=override):
                with patch.dict(os.environ, {"PATH": str(self.root), **override}, clear=True):
                    self.assertEqual(require_pi(), str(self.executable))
        with patch.dict(os.environ, {"PATH": str(self.dependencies)}, clear=True):
            with self.assertRaisesRegex(SystemExit, "Pi is required for loader regressions"):
                require_pi()

    def test_resources_are_resolved_at_call_time_not_cached(self):
        second = self.root / "other-pi"
        second.write_bytes(self.executable.read_bytes())
        second.chmod(0o755)
        with patch.dict(os.environ, {"PI_BIN": str(self.executable)}, clear=True):
            self.assertEqual(require_pi(), str(self.executable))
            os.environ["PI_BIN"] = str(second)
            self.assertEqual(require_pi(), str(second))
        with patch.dict(os.environ, {"PI_WEB_FETCH_DIR": str(self.dependencies)}, clear=True):
            self.assertEqual(require_web_fetch_dependencies(), self.dependencies)
            os.environ["PI_WEB_FETCH_DIR"] = str(self.root / "missing")
            with self.assertRaisesRegex(SystemExit, "Managed web-fetch dependencies are required"):
                require_web_fetch_dependencies()

    def test_web_dependencies_default_to_current_home_and_need_node_modules(self):
        home = self.root / "home"
        expected = home / ".pi/agent/extensions/web-fetch"
        (expected / "node_modules").mkdir(parents=True)
        with patch.dict(os.environ, {"HOME": str(home)}, clear=True):
            self.assertEqual(require_web_fetch_dependencies(), expected)
            (expected / "node_modules").rmdir()
            (expected / "node_modules").write_text("not a directory")
            with self.assertRaisesRegex(SystemExit, "Managed web-fetch dependencies are required"):
                require_web_fetch_dependencies()

    def test_relative_overrides_resolve_before_fixture_cwd_changes(self):
        # A private subprocess avoids changing the unittest runner's cwd.
        env = dict(os.environ, PI_BIN="pi", PI_WEB_FETCH_DIR="web-fetch")
        result = self.run_python(
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from pi_test_support import require_pi, require_web_fetch_dependencies; "
            "print(require_pi()); print(require_web_fetch_dependencies())",
            env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.executable), str(self.dependencies)])

    def test_isolation_removes_live_identity_without_erasing_resource_configuration(self):
        inherited = {
            "HERDR_ENV": "1",
            "HERDR_SOCKET_PATH": "/fixture/live.sock",
            "HERDR_FUTURE_SETTING": "live",
            "PI_SUBAGENT": "live",
            "PI_SUBAGENT_SESSION": "/fixture/live.jsonl",
            "PI_SUBAGENT_FUTURE_SETTING": "live",
            "TMUX": "live-server",
            "TMUX_PANE": "%99",
            "TMUX_OTHER": "keep",
            "PATH": str(self.root),
            "HOME": str(self.root),
            "PI_BIN": str(self.executable),
            "PI_WEB_FETCH_DIR": str(self.dependencies),
            "PI_CODING_AGENT_DIR": "/fixture/caller-agent",
            "PI_TEST_KEEP": "fixture",
            "OTHER_CONFIG": "keep",
        }
        with patch.dict(os.environ, inherited, clear=True):
            isolated = isolated_environment()
            self.assertEqual(dict(os.environ), inherited, "Isolation mutated the caller")
        expected = {
            key: value
            for key, value in inherited.items()
            if not key.startswith(("HERDR_", "PI_SUBAGENT")) and key not in {"TMUX", "TMUX_PANE"}
        }
        self.assertEqual(isolated, expected)
        isolated.update(HERDR_ENV="1", HERDR_SOCKET_PATH="/fixture/private.sock")
        self.assertEqual(inherited["HERDR_SOCKET_PATH"], "/fixture/live.sock")
        self.assertEqual(isolated["HERDR_SOCKET_PATH"], "/fixture/private.sock")

    def test_helper_and_suites_import_without_resource_checks_from_nonrepo_cwd(self):
        result = self.run_python(
            """
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch
with patch('shutil.which', side_effect=AssertionError('eager executable lookup')), \\
     patch('pathlib.Path.home', side_effect=AssertionError('eager home lookup')), \\
     patch('pathlib.Path.is_dir', side_effect=AssertionError('eager dependency validation')), \\
     patch('pathlib.Path.is_file', side_effect=AssertionError('eager executable validation')), \\
     patch('os.access', side_effect=AssertionError('eager executable validation')):
    for name in ['pi_test_support', 'pi-subagents', 'pi-extensions', 'pi-herdr', 'pi-herdr-reporting']:
        spec = importlib.util.spec_from_file_location(name, Path(sys.argv[1]) / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
""",
            dict(os.environ, PI_BIN="/missing/pi", PI_WEB_FETCH_DIR="/missing/web-fetch"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def run_python(self, source, env):
        return subprocess.run(
            [sys.executable, "-B", "-c", source, str(TESTS)],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_direct_and_preflight_diagnostics_match(self):
        blocked = self.root / "not-executable"
        blocked.write_text("fixture")
        blocked.chmod(0o644)
        cases = [
            ({"PI_BIN": str(blocked)}, "require_pi"),
            ({"PI_BIN": str(self.root / "missing")}, "require_pi"),
            ({"PI_BIN": str(self.dependencies)}, "require_pi"),
            ({"PATH": str(self.dependencies), "PI_BIN": ""}, "require_pi"),
            ({"PI_WEB_FETCH_DIR": str(self.root / "missing")}, "require_web_fetch_dependencies"),
        ]
        for overrides, function in cases:
            with self.subTest(overrides=overrides):
                env = dict(
                    os.environ,
                    PI_BIN=str(self.executable),
                    PI_WEB_FETCH_DIR=str(self.dependencies),
                )
                env.update(overrides)
                direct = self.run_python(
                    f"import sys; sys.path.insert(0, sys.argv[1]); "
                    f"from pi_test_support import {function}; {function}()",
                    env,
                )
                preflight = subprocess.run(
                    [sys.executable, "-B", str(TESTS / "pi_test_support.py")],
                    cwd=self.root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(direct.returncode, 1, direct.stderr)
                self.assertEqual(preflight.returncode, direct.returncode)
                self.assertEqual(preflight.stderr, direct.stderr)
                # Direct standalone suites report the same resource diagnostic.
                suite, test = (
                    ("pi-subagents", "PiRegressions.test_recovered_retry_does_not_publish_failure")
                    if function == "require_pi"
                    else (
                        "pi-extensions",
                        "Extensions.test_pdf_uses_packaged_pdfjs_through_pi_loader",
                    )
                )
                standalone = subprocess.run(
                    [sys.executable, "-B", str(TESTS / (suite + ".py")), test],
                    cwd=self.root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(standalone.returncode, 1, standalone.stderr)
                self.assertIn(direct.stderr.strip(), standalone.stderr)

    def test_preflight_success_uses_overrides_without_running_pi(self):
        self.executable.write_text("#!/bin/sh\nexit 99\n")
        result = subprocess.run(
            [sys.executable, "-B", str(TESTS / "pi_test_support.py")],
            cwd=self.root,
            env=dict(
                os.environ, PI_BIN=str(self.executable), PI_WEB_FETCH_DIR=str(self.dependencies)
            ),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout + result.stderr, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
