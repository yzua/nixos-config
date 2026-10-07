#!/usr/bin/env python3
"""Offline regression tests for the pinned static REA route; no engine/model calls."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "home-manager/modules/ai/pi-re"
sys.path.insert(0, str(CODE))
spec = importlib.util.spec_from_file_location("pi_re_rea", CODE / "rea.py")
rea = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rea)


class ReaTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.locations = {"state": self.root / "state"}
        self.config = {
            "rea": {
                "cli": str(self.root / "bin/rea"),
                "ghidra": str(self.root / "ghidra"),
                "jdk": str(self.root / "jdk"),
                "jadxJar": str(self.root / "jadx.jar"),
            }
        }
        for relative in (
            "bin/rea",
            "ghidra/support/analyzeHeadless",
            "jdk/bin/java",
            "jdk/bin/javac",
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture")
            path.chmod(0o755)
        (self.root / "jadx.jar").write_text("fixture")

    def test_pinned_engines_private_home_and_no_ambient_runtime_injection(self):
        environment = {
            "HOME": "/coding",
            "PATH": "/ambient/bin",
            "TMPDIR": "/tmp/unsafe space",
            "REA_ANALYSIS_PROVIDER": "ida",
            "REA_IDA_MCP_CONFIG": "/private/config",
            "REA_JADX_MCP_JAR": "/other.jar",
            "HOPPER_LAUNCHER_PATH": "/other/hopper",
            "GHIDRA_INSTALL_DIR": "/other/ghidra",
            "JAVA_HOME": "/other/jdk",
            "NODE_OPTIONS": "--import /ambient.js",
            "NODE_PATH": "/ambient",
            "JAVA_TOOL_OPTIONS": "-javaagent:/ambient.jar",
            "_JAVA_OPTIONS": "bad",
            "JDK_JAVA_OPTIONS": "bad",
            "GHIDRA_JAVA_OPTIONS": "bad",
        }
        argv, env = rea.command(
            self.config,
            self.locations,
            ["function", "/owned/fixture", "leaf", "--provider", "ghidra", "--json"],
            environment,
        )
        self.assertEqual(argv[0], self.config["rea"]["cli"])
        self.assertEqual(argv[1], "function")
        self.assertEqual(env["GHIDRA_INSTALL_DIR"], self.config["rea"]["ghidra"])
        self.assertEqual(env["JAVA_HOME"], self.config["rea"]["jdk"])
        self.assertEqual(env["REA_JADX_MCP_JAR"], self.config["rea"]["jadxJar"])
        self.assertEqual(env["REA_ANALYSIS_PROVIDER"], "auto")
        self.assertEqual(env["TMPDIR"], "/tmp")
        self.assertEqual(env["NO_UPDATE_NOTIFIER"], "1")
        self.assertNotEqual(env["HOME"], environment["HOME"])
        self.assertTrue(env["PATH"].startswith(self.config["rea"]["jdk"] + "/bin:"))
        for key in (
            "NODE_OPTIONS",
            "NODE_PATH",
            "JAVA_TOOL_OPTIONS",
            "_JAVA_OPTIONS",
            "HOPPER_LAUNCHER_PATH",
            "REA_IDA_MCP_CONFIG",
        ):
            self.assertNotIn(key, env)
        for key in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
            path = Path(env[key])
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            self.assertTrue(path.is_relative_to(self.locations["state"]))
        self.assertEqual(environment["HOME"], "/coding")

    def test_install_mcp_runtime_and_unknown_routes_rejected_before_state(self):
        for args in (
            ["setup"],
            ["update"],
            ["uninstall"],
            ["mcp"],
            ["--mcp"],
            ["capture-process", "scenario.json"],
            ["capture-browser-scenario", "scenario.json"],
            ["function", "target", "leaf", "--mcp"],
            ["unknown"],
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                rea.command(self.config, self.locations, args, {})
        self.assertFalse(self.locations["state"].exists())

    def test_global_updater_flags_rejected_on_every_allowed_route_before_state(self):
        for route in rea.COMMANDS | rea.HELP:
            for flag in (
                "--update",
                "--update=true",
                "--incur-update-check",
                "--incur-update-check=true",
            ):
                with (
                    self.subTest(route=route, flag=flag),
                    self.assertRaisesRegex(ValueError, "Nix owns"),
                ):
                    rea.command(self.config, self.locations, [route, flag], {})
        self.assertFalse(self.locations["state"].exists())

    def test_missing_engine_blocks_before_creating_state(self):
        (self.root / "jadx.jar").unlink()
        with self.assertRaisesRegex(ValueError, "Android engine unavailable"):
            rea.command(self.config, self.locations, ["--version"], {})
        self.assertFalse(self.locations["state"].exists())

    def test_symlink_state_rejected(self):
        (self.root / "foreign").mkdir()
        self.locations["state"].symlink_to(self.root / "foreign", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            rea.command(self.config, self.locations, ["--help"], {})
        self.assertEqual(list((self.root / "foreign").iterdir()), [])

    def test_empty_args_are_help_and_json_args_are_unchanged(self):
        argv, _ = rea.command(self.config, self.locations, [], {})
        self.assertEqual(argv[1:], ["--help"])
        args = ["inspect-android-method", "/apk", "Class", "run", "--overload-index", "1", "--json"]
        argv, _ = rea.command(self.config, self.locations, args, {})
        self.assertEqual(argv[1:], args)

    def test_runtime_lock_preserves_release_pins_without_dev_dependencies(self):
        lock = json.loads((ROOT / "packages/rea/package-lock.json").read_text())
        self.assertEqual(lock["version"], "4.1.0")
        self.assertNotIn("devDependencies", lock["packages"][""])
        self.assertFalse(any(item.get("dev") for item in lock["packages"].values()))
        for name, item in lock["packages"].items():
            if name:
                self.assertTrue(item["resolved"].startswith("https://registry.npmjs.org/"))
                self.assertTrue(item["integrity"].startswith("sha512-"))

    def test_prompts_and_domain_skills_route_to_reviewed_backend(self):
        self.assertIn('"rea-analysis"', (CODE / "launcher.py").read_text())
        self.assertIn("pi-re rea", (CODE / "contract.md").read_text())
        for name in ("re-map", "re-build", "re-prove"):
            prompt = (CODE / f"prompts/{name}.md").read_text()
            self.assertIn("rea-analysis", prompt)
            self.assertIn("pi-re rea", prompt)
        for name in ("native-analysis", "android-static"):
            self.assertIn("rea-analysis", (CODE / f"skills/{name}/SKILL.md").read_text())
        self.assertIn("REA", (CODE / "prompts/re-handoff.md").read_text())


if __name__ == "__main__":
    unittest.main()
