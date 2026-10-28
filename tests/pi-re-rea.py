#!/usr/bin/env python3
"""Offline regression tests for the pinned static REA route; no engine/model calls."""

import contextlib
import hashlib
import importlib.util
import io
import json
import selectors
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "home-manager/modules/ai/pi-re"
RELEASE = json.loads((ROOT / "tests/fixtures/pi-re-rea/release-inventory.json").read_text())
sys.path.insert(0, str(CODE))
spec = importlib.util.spec_from_file_location("pi_re_rea", CODE / "rea.py")
rea = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rea)
adb_spec = importlib.util.spec_from_file_location("pi_re_rea_adb", CODE / "rea_adb.py")
rea_adb = importlib.util.module_from_spec(adb_spec)
adb_spec.loader.exec_module(rea_adb)


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
        self.assertEqual(env["REA_ANALYSIS_PROVIDER"], "ghidra")
        self.assertEqual(env["PI_RE_STATE_DIR"], str(self.locations["state"]))
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

    def test_analysis_controls_preserved_but_engine_injection_rejected(self):
        settings = {
            "REA_GHIDRA_LANGUAGE_ID": "MIPS:BE:32:default",
            "REA_GHIDRA_COMPILER_SPEC_ID": "default",
            "REA_GHIDRA_SEED_FILE": "/owned/seeds.tsv",
            "REA_GHIDRA_STARTUP_TIMEOUT_MS": "420000",
            "REA_GHIDRA_DISABLED_ANALYZERS": "DWARF",
            "REA_GHIDRA_DECOMPILE_TIMEOUT_SECONDS": "90",
            "REA_JADX_OPERATION_TIMEOUT_MS": "180000",
            "REA_MCP_INPUT_SCHEMA_PROFILE": "full",
            "REA_REFERENCE_SECRET_PATTERNS_JSON": '["private/**", "*.env"]',
        }
        _, env = rea.command(
            self.config,
            self.locations,
            ["--help"],
            settings
            | {
                "REA_BROWSER_EXECUTABLE": "/ambient/browser",
                "REA_GHIDRA_NATIVEAOT_JAR": "/ambient/plugin.jar",
            },
        )
        for key, value in settings.items():
            self.assertEqual(env[key], value)
        self.assertNotIn("REA_BROWSER_EXECUTABLE", env)
        self.assertNotIn("REA_GHIDRA_NATIVEAOT_JAR", env)

    def test_install_transport_and_unknown_routes_rejected_before_state(self):
        for args in (
            ["setup"],
            ["update"],
            ["uninstall"],
            ["mcp"],
            ["--mcp"],
            ["function", "target", "leaf", "--mcp"],
            ["unknown"],
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                rea.command(self.config, self.locations, args, {})
        self.assertFalse(self.locations["state"].exists())

    def test_network_runtime_routes_and_pinned_mcp_transport(self):
        for args in (
            ["inspect-web-network-capture", "capture.har", "har", "--json"],
            ["capture-process", "scenario.json", "--json"],
            ["capture-browser-scenario", "scenario.json", "--json"],
            ["inspect-analysis-view", "request.json", "--json"],
            ["inspect-sqlite-database", "snapshot.sqlite", "--json"],
            ["inspect-packet-capture", "owned.pcap", "--json"],
            ["inspect-pcap-capture", "owned.pcap", "--json"],
            ["inspect-rust-binary", "owned.elf", "--json"],
            ["identify-flutter-build", "owned.apk", "--json"],
            ["inspect-with-objdump", "owned.elf", "--json"],
        ):
            argv, _ = rea.command(self.config, self.locations, args, {})
            self.assertEqual(argv[1:], args)
        self.config["rea"]["environment"] = {"REA_MITMDUMP_COMMAND": "/pinned/mitmdump"}
        argv, env = rea.command(self.config, self.locations, [], {}, mcp=True)
        self.assertEqual(argv[1:], ["--mcp"])
        self.assertEqual(env["REA_MITMDUMP_COMMAND"], "/pinned/mitmdump")
        with self.assertRaisesRegex(ValueError, "takes no arguments"):
            rea.command(self.config, self.locations, ["--update"], {}, mcp=True)

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
        self.assertEqual(lock["version"], RELEASE["version"])
        self.assertNotIn("devDependencies", lock["packages"][""])
        self.assertFalse(any(item.get("dev") for item in lock["packages"].values()))
        for name, item in lock["packages"].items():
            if name:
                self.assertTrue(item["resolved"].startswith("https://registry.npmjs.org/"))
                self.assertTrue(item["integrity"].startswith("sha512-"))

    def test_release_inventory_and_managed_packet_tools(self):
        self.assertEqual(len(rea.COMMANDS), RELEASE["cli_count"])
        digest = hashlib.sha256(("\n".join(sorted(rea.COMMANDS)) + "\n").encode()).hexdigest()
        self.assertEqual(digest, RELEASE["cli_names_sha256"])
        self.assertTrue(
            {
                "search-bytes",
                "inspect-signal-decoders",
                "decode-signal-recording",
                "inspect-wasm-artifact",
                "compare-wasm-interfaces",
                "inspect-electron-fuses",
                "project-harmony-application-graph",
                "instrument-with-frida",
            }
            <= rea.COMMANDS
        )
        module = (CODE / "default.nix").read_text()
        for setting in (
            'REA_TSHARK_COMMAND = "${pkgs.wireshark-cli}/bin/tshark"',
            'REA_CAPINFOS_COMMAND = "${pkgs.wireshark-cli}/bin/capinfos"',
            'REA_TSHARK_PRLIMIT_COMMAND = "${pkgs.util-linux}/bin/prlimit"',
            'REA_OBJDUMP_COMMAND = "${pkgs.binutils}/bin/objdump"',
        ):
            self.assertIn(setting, module)
        package = (ROOT / "packages/rea/default.nix").read_text()
        self.assertIn('npmFlags = [ "--ignore-scripts" ]', package)

    def test_adb_transport_selects_owned_root_and_sanitizes_enumeration(self):
        lab = MagicMock()
        lab.serial = "emulator-5678"
        lab.env = {"ADB_SERVER_SOCKET": "tcp:localhost:5037"}
        lab.lock.side_effect = lambda: contextlib.nullcontext()
        lab.adb.return_value = (0, "0\n")
        execute = MagicMock(
            return_value=subprocess.CompletedProcess(
                [], 0, "List of devices attached\nemulator-5678 device\nforeign device\n", ""
            )
        )
        config = {"android": {"adb": "/pinned/adb"}}
        with patch.object(rea_adb, "Android", return_value=lab):
            with self.assertRaisesRegex(rea_adb.LabError, "selected"):
                rea_adb.run(config, self.root, ["-s", "foreign", "shell", "id"], execute=execute)
            execute.assert_not_called()
            with contextlib.redirect_stdout(io.StringIO()) as output:
                rea_adb.run(config, self.root, ["devices", "-l"], execute=execute)
            self.assertNotIn("foreign", output.getvalue())
            self.assertEqual(execute.call_args.kwargs["env"], lab.env)
            rea_adb.run(config, self.root, ["version"], execute=execute)
            self.assertEqual(execute.call_args.kwargs["env"], lab.env)
            rea_adb.run(
                config, self.root, ["-s", lab.serial, "pull", "/owned", "/copy"], execute=execute
            )
            lab.device_identity.assert_called_once()
            self.assertEqual(execute.call_args.kwargs["timeout"], 600)
            lab.adb.return_value = (0, "2000\n")
            execute.reset_mock()
            with self.assertRaisesRegex(rea_adb.LabError, "already rooted"):
                rea_adb.run(config, self.root, ["-s", lab.serial, "shell", "id"], execute=execute)
            execute.assert_not_called()

    def test_adb_cancellation_reaps_resistant_client_before_outer_escalation(self):
        script = (
            f"import sys;sys.path.insert(0,{str(CODE)!r});import rea_adb;"
            "rea_adb.owned_run([sys.executable,'-c',"
            "'import os,time,signal;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
            "print(os.getpid(),flush=True);time.sleep(60)'],timeout=90)"
        )
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", script], stdout=subprocess.PIPE, text=True
        )
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            self.assertTrue(selector.select(10), "Owned ADB stand-in did not start")
            child_pid = int(process.stdout.readline())
            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=4), 128 + signal.SIGTERM)
            self.assertFalse(Path(f"/proc/{child_pid}").exists(), "ADB child escaped cancellation")
        finally:
            selector.close()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            process.stdout.close()

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
        native = (CODE / "skills/native-analysis/SKILL.md").read_text()
        self.assertIn("persistent MCP", native)
        self.assertNotIn("Prefer the provisioned `pi-re rea` CLI", native)


if __name__ == "__main__":
    unittest.main()
