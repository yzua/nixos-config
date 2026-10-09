#!/usr/bin/env python3
"""Check prepared skills and local installation without touching the live home or network."""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "home-manager/modules/ai/skills.py"
UI_COMMAND = 'python "${CLAUDE_PLUGIN_ROOT}/.claude/skills/ui-ux-pro-max/scripts/search.py"'


class SkillsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skills-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home with 'quotes and $dollars"
        self.home.mkdir()
        self.bundle = self.root / "bundle"
        self.manifest = self.root / "sources.json"
        self.environment = {
            "HOME": str(self.home),
            "PATH": os.environ["PATH"],
            "DISABLE_TELEMETRY": "1",
            "CI": "1",
        }
        self.source = self.root / "source"
        self.source.mkdir()
        self.skill(self.source, "fixture")
        self.manifest.write_text(
            json.dumps(
                [{"path": str(self.source), "skill": "*", "url": "https://fixture.invalid/pin"}]
            )
        )
        self.log = self.root / "calls.jsonl"
        self.cli = self.root / "fake-skills"
        self.cli.write_text(
            f"#!{sys.executable}\n"
            "import json, os, stat, sys\nfrom pathlib import Path\n"
            "source = Path(sys.argv[2])\n"
            "files = list(source.rglob('SKILL.md'))\n"
            "assert files and all(p.stat().st_mode & stat.S_IWUSR for p in files)\n"
            "with open(os.environ['SKILLS_TEST_LOG'], 'a') as log:\n"
            " log.write(json.dumps({'args': sys.argv[1:], 'texts': [p.read_text() for p in files]}) + '\\n')\n"
            "sys.exit(int(os.environ.get('SKILLS_TEST_EXIT', '0')))\n"
        )
        self.cli.chmod(0o700)
        self.environment["SKILLS_TEST_LOG"] = str(self.log)

    def skill(self, directory, name, body="Fixture instructions."):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: A test fixture\n---\n{body}\n"
        )

    def run_script(self, *arguments, **environment):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *map(str, arguments)],
            env=dict(self.environment, **environment),
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=30,
        )

    def prepare(self):
        result = self.run_script("prepare", self.manifest, self.bundle)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_prepare_records_pins_without_mutating_source(self):
        before = (self.source / "SKILL.md").read_bytes()
        self.prepare()
        manifest = json.loads((self.bundle / "manifest.json").read_text())
        self.assertEqual(
            manifest,
            [{"directory": "source-0", "skill": "*", "url": "https://fixture.invalid/pin"}],
        )
        self.assertEqual((self.bundle / "source-0/SKILL.md").read_bytes(), before)
        self.assertEqual((self.source / "SKILL.md").read_bytes(), before)

    def test_invalid_later_source_fails_before_preparation(self):
        sources = json.loads(self.manifest.read_text())
        sources.append({"path": str(self.root / "missing"), "skill": "*", "url": "fixture"})
        self.manifest.write_text(json.dumps(sources))
        result = self.run_script("prepare", self.manifest, self.bundle)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.bundle.exists())
        self.assertFalse(self.log.exists())

    def test_ui_repair_targets_final_mutable_copy(self):
        ui = self.source / "ui-ux-pro-max"
        self.skill(ui, "ui-ux-pro-max", UI_COMMAND)
        (ui / "scripts").mkdir()
        (ui / "scripts/search.py").write_text("print('fixture')\n")
        sources = json.loads(self.manifest.read_text())
        sources[0]["repairUiSearch"] = True
        self.manifest.write_text(json.dumps(sources))
        before = (ui / "SKILL.md").read_bytes()
        self.prepare()
        repaired = (self.bundle / "source-0/ui-ux-pro-max/SKILL.md").read_text()
        self.assertNotIn("CLAUDE_PLUGIN_ROOT", repaired)
        self.assertIn("${HOME}/.agents/skills/ui-ux-pro-max/scripts/search.py", repaired)
        self.assertIn(f"{sys.executable} -B", repaired)
        self.assertNotIn(str(self.bundle), repaired)
        self.assertNotIn(str(self.source), repaired)
        self.assertEqual((ui / "SKILL.md").read_bytes(), before)

    def test_changed_ui_command_or_missing_script_fails_preparation(self):
        ui = self.source / "ui-ux-pro-max"
        self.skill(ui, "ui-ux-pro-max", "Upstream changed.")
        (ui / "scripts").mkdir()
        script = ui / "scripts/search.py"
        script.write_text("fixture")
        sources = json.loads(self.manifest.read_text())
        sources[0]["repairUiSearch"] = True
        self.manifest.write_text(json.dumps(sources))
        for missing_script in (False, True):
            with self.subTest(missing_script=missing_script):
                if missing_script:
                    script.unlink()
                result = self.run_script(
                    "prepare", self.manifest, self.root / f"invalid-{missing_script}"
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.log.exists())

    def test_install_stages_writable_sources_and_preserves_flags(self):
        self.prepare()
        skill = self.bundle / "source-0/SKILL.md"
        skill.chmod(0o444)
        self.assertEqual(self.run_script("install", self.bundle, self.cli).returncode, 0)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len(calls), 1)
        args = calls[0]["args"]
        self.assertEqual(args[0], "add")
        self.assertEqual(args[2:], ["--global", "--agent", "*", "--skill", "*", "--yes"])
        self.assertFalse(Path(args[1]).exists(), "Staging directory must be cleaned")
        self.assertEqual(skill.stat().st_mode & 0o777, 0o444)

    def test_invalid_later_bundle_does_not_start_installer(self):
        self.prepare()
        manifest = json.loads((self.bundle / "manifest.json").read_text())
        manifest.append({"directory": "missing", "skill": "*", "url": "fixture"})
        (self.bundle / "manifest.json").write_text(json.dumps(manifest))
        result = self.run_script("install", self.bundle, self.cli)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_dry_run_does_not_read_bundle_or_invoke_installer(self):
        result = self.run_script("install", self.root / "missing", self.cli, DRY_RUN="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Would sync", result.stdout)
        self.assertFalse(self.log.exists())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_installer_failure_propagates_and_cleans_staging(self):
        self.prepare()
        result = self.run_script("install", self.bundle, self.cli, SKILLS_TEST_EXIT="17")
        self.assertNotEqual(result.returncode, 0)
        call = json.loads(self.log.read_text().strip())
        self.assertFalse(Path(call["args"][1]).exists())

    def test_prepared_directory_cannot_escape_bundle(self):
        self.prepare()
        for directory in ("..", "../source", str(self.source), ".", ""):
            with self.subTest(directory=directory):
                (self.bundle / "manifest.json").write_text(
                    json.dumps([{"directory": directory, "skill": "*", "url": "fixture"}])
                )
                result = self.run_script("install", self.bundle, self.cli)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.log.exists())

    def test_real_local_installer_keeps_writable_copies_links_and_unrelated_skills(self):
        cli = shutil.which("skills")
        self.assertIsNotNone(
            cli, "Managed skills CLI is required for the offline local-source test"
        )
        self.prepare()
        (self.bundle / "source-0/SKILL.md").chmod(0o444)
        unrelated = self.home / ".agents/skills/unrelated/SKILL.md"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("User-owned instructions.")
        # Positive environment allowlist prevents custom agent roots from leaking
        # out of the temporary HOME. Block network even if upstream behavior changes.
        guard = self.root / "deny-network.cjs"
        guard.write_text(
            "globalThis.fetch = () => { throw new Error('OFFLINE_NETWORK_FORBIDDEN'); };\n"
            "const net = require('node:net');\n"
            "net.Socket.prototype.connect = () => { throw new Error('OFFLINE_SOCKET_FORBIDDEN'); };\n"
        )
        bindir = self.root / "bin"
        bindir.mkdir()
        for command in ("git", "gh", "curl", "wget"):
            shim = bindir / command
            shim.write_text("#!/bin/sh\necho OFFLINE_COMMAND_FORBIDDEN >&2\nexit 99\n")
            shim.chmod(0o700)
        environment = {
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "NODE_OPTIONS": f"--require={guard}",
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_STATE_HOME": str(self.home / ".local/state"),
        }
        for _ in range(2):
            result = self.run_script("install", self.bundle, cli, **environment)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("OFFLINE_", result.stdout + result.stderr)
        installed = self.home / ".agents/skills/fixture/SKILL.md"
        self.assertTrue(installed.stat().st_mode & stat.S_IWUSR)
        self.assertEqual(installed.read_text(), (self.source / "SKILL.md").read_text())
        pi = self.home / ".pi/agent/skills/fixture"
        self.assertTrue(pi.is_symlink())
        self.assertEqual(pi.resolve(), installed.parent)
        self.assertEqual(unrelated.read_text(), "User-owned instructions.")


if __name__ == "__main__":
    unittest.main()
