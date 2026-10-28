#!/usr/bin/env python3
"""Exercise the read-only skill inventory with isolated local fixtures."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "home-manager/modules/ai/skills/skill-audit"
SCRIPT = SKILL / "scripts/inventory.py"
spec = importlib.util.spec_from_file_location("skill_inventory", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class SkillAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skill-audit-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "home with 'quotes and $dollars"
        self.root.mkdir()
        self.skills = self.root / ".agents/skills"
        self.skills.mkdir(parents=True)
        self.project = self.root / "project"
        self.project.mkdir()

    def skill(self, directory, name="fixture", description="Fixture instructions"):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "SKILL.md"
        path.write_text(f"---\nname: {name}\ndescription: {description}\n---\nRead local docs.\n")
        return path

    def run_inventory(self, *roots):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *map(str, roots)],
            cwd=self.project,
            env={"HOME": str(self.root), "PATH": os.environ["PATH"]},
            text=True,
            capture_output=True,
            timeout=10,
        )

    def snapshot(self):
        return {
            str(path.relative_to(self.root)): (
                path.lstat().st_mtime_ns,
                path.readlink().as_posix() if path.is_symlink() else path.read_bytes(),
            )
            for path in self.root.rglob("*")
            if path.is_symlink() or path.is_file()
        }

    def test_aliases_are_not_duplicate_skills_and_scan_is_read_only(self):
        skill = self.skill(self.skills / "fixture")
        aliases = self.root / ".claude/skills"
        aliases.mkdir(parents=True)
        (aliases / "fixture").symlink_to(skill.parent, target_is_directory=True)
        before = self.snapshot()
        result = self.run_inventory(self.skills, aliases)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["skills"]), 1)
        self.assertEqual(data["skills"][0]["path"], str(skill))
        self.assertEqual(len(data["skills"][0]["discovered_paths"]), 2)
        self.assertEqual(data["duplicate_names"], {})
        self.assertEqual(data["errors"], [])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_inventory(self.skills, aliases).stdout, result.stdout)

    def test_same_root_aliases_include_nested_skill_paths(self):
        skill = self.skill(self.skills / "original/nested")
        alias = self.skills / "alias"
        alias.symlink_to(skill.parent.parent, target_is_directory=True)
        result = self.run_inventory(self.skills)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["skills"]), 1)
        self.assertEqual(
            set(data["skills"][0]["discovered_paths"]),
            {str(skill), str(alias / "nested/SKILL.md")},
        )
        self.assertEqual(data["duplicate_names"], {})

    def test_dangling_installer_link_is_reported(self):
        self.skill(self.skills / "good")
        broken = self.skills / "retired"
        broken.symlink_to(self.root / "deleted-skill", target_is_directory=True)
        result = self.run_inventory(self.skills)
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["skills"]), 1)
        self.assertEqual(data["errors"], [{"path": str(broken), "error": "broken symlink"}])
        self.assertEqual(data["roots"][0]["status"], "error")

    def test_distinct_files_with_same_declared_name_are_reported(self):
        first = self.skill(self.skills / "first", name="same")
        second = self.skill(self.skills / "second", name="same")
        result = self.run_inventory(self.skills)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["duplicate_names"], {"same": [str(first), str(second)]})

    def test_defaults_list_missing_roots_and_find_shared_skills(self):
        self.skill(self.skills / "fixture")
        result = self.run_inventory()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["roots"]), 8)
        self.assertEqual(data["roots"][0]["status"], "scanned")
        self.assertTrue(any(root["status"] == "missing" for root in data["roots"]))
        self.assertEqual(len(data["skills"]), 1)

    def test_cycles_and_archive_directories_are_skipped(self):
        self.skill(self.skills / "fixture")
        self.skill(self.skills / ".trash/retired", name="retired")
        (self.skills / "fixture/loop").symlink_to(self.skills, target_is_directory=True)
        result = self.run_inventory(self.skills)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["skills"]), 1)

    def test_read_errors_are_reported_without_losing_good_entries(self):
        self.skill(self.skills / "good")
        bad = self.skills / "bad/SKILL.md"
        bad.parent.mkdir()
        bad.write_bytes(b"\xff")
        result = self.run_inventory(self.skills)
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["skills"]), 1)
        self.assertEqual(len(data["errors"]), 1)
        self.assertEqual(data["roots"][0]["status"], "error")

    def test_broken_skill_and_root_symlinks_are_errors(self):
        broken = self.skills / "broken/SKILL.md"
        broken.parent.mkdir()
        broken.symlink_to(self.root / "absent")
        alias = self.root / "broken-root"
        alias.symlink_to(self.root / "absent", target_is_directory=True)
        result = self.run_inventory(self.skills, alias)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(json.loads(result.stdout)["errors"]), 2)

    def test_missing_metadata_and_block_descriptions(self):
        fields, issues = audit.metadata("Instructions without frontmatter")
        self.assertEqual(fields, {})
        self.assertIn("frontmatter", issues[0])
        for marker in (">", "|-", ">-"):
            fields, issues = audit.metadata(
                f"---\nname: 'fixture'\ndescription: {marker}\n  First line\n  second line\n---\n"
            )
            self.assertEqual(fields["name"], "fixture")
            self.assertEqual(fields["description"], "First line second line")
            self.assertEqual(issues, [])
        _, issues = audit.metadata("---\nname: fixture\n---\n")
        self.assertEqual(issues, ["missing description"])

    def test_workflows_have_routing_evidence_and_safety_contracts(self):
        instructions = (ROOT / "home-manager/modules/ai/pi-base/AGENTS.md").read_text()
        self.assertIn("**Reuse first.**", instructions)
        self.assertIn("existing dependencies", instructions)
        self.assertIn("Criterion | Check (command or source) | Result", instructions)
        for status in ("PASS", "FAIL", "NOT RUN", "N/A"):
            self.assertIn(status, instructions)
        prompt = (ROOT / "home-manager/modules/ai/pi-coding/prompts/verify.md").read_text()
        self.assertIn("Keep source files untouched", prompt)
        self.assertIn("loaded working preferences", prompt)
        skill = (SKILL / "SKILL.md").read_text()
        self.assertIn("scripts/inventory.py", skill)
        self.assertIn("unmeasured", skill)
        self.assertIn("ask before modifying", skill)
        sources = (ROOT / "home-manager/modules/ai/skills.nix").read_text()
        self.assertIn("path = ./skills/skill-audit;", sources)
        self.assertIn('url = "repo:home-manager/modules/ai/skills/skill-audit";', sources)


if __name__ == "__main__":
    unittest.main()
