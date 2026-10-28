#!/usr/bin/env python3
"""Inventory skill files without changing them, executing them, or accessing the network."""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

SKIP_DIRECTORIES = {".git", ".trash", "__pycache__", "node_modules"}


def metadata(text):
    """Read only the two routing fields; leave full YAML validation to the host."""
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return {}, ["missing or unclosed frontmatter"]
    fields = {}
    header = lines[1 : lines[1:].index("---") + 1]
    for index, line in enumerate(header):
        match = re.match(r"^(name|description):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        if value in {">", "|", ">-", "|-", ">+", "|+"}:
            continuation = []
            for following in header[index + 1 :]:
                if following and not following[0].isspace():
                    break
                continuation.append(following.strip())
            value = " ".join(continuation).strip()
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key] = value
    issues = [f"missing {key}" for key in ("name", "description") if not fields.get(key)]
    return fields, issues


def inventory(roots):
    skills = {}
    errors = []
    root_reports = []
    for root in roots:
        report = {"path": str(root), "status": "scanned"}
        root_reports.append(report)
        if not root.exists():
            report["status"] = "missing"
            if root.is_symlink():
                errors.append({"path": str(root), "error": "broken root symlink"})
            continue
        if not root.is_dir():
            report["status"] = "error"
            errors.append({"path": str(root), "error": "not a directory"})
            continue
        ancestors = {root: frozenset()}

        def walk_error(error):
            errors.append({"path": str(error.filename), "error": str(error)})
            report["status"] = "error"

        # Preserve alias paths; stop only links back into the current ancestor chain.
        for directory, directories, files in os.walk(root, followlinks=True, onerror=walk_error):
            path = Path(directory)
            try:
                physical = path.resolve(strict=True)
                parents = ancestors.pop(path, frozenset())
                if physical in parents:
                    directories[:] = []
                    continue
                directories[:] = sorted(set(directories) - SKIP_DIRECTORIES)
                for child in directories:
                    ancestors[path / child] = parents | {physical}
                for filename in sorted(set(files) - {"SKILL.md"} - SKIP_DIRECTORIES):
                    child = path / filename
                    if child.is_symlink() and not child.exists():
                        errors.append({"path": str(child), "error": "broken symlink"})
                        report["status"] = "error"
                if "SKILL.md" not in files:
                    continue
                skill = path / "SKILL.md"
                resolved = skill.resolve(strict=True)
                if str(resolved) in skills:
                    skills[str(resolved)]["discovered_paths"].append(str(skill))
                    continue
                content = skill.read_bytes()
                text = content.decode("utf-8")
                fields, issues = metadata(text)
                skills[str(resolved)] = {
                    "path": str(resolved),
                    "discovered_paths": [str(skill)],
                    "name": fields.get("name"),
                    "description": fields.get("description"),
                    "lines": len(text.splitlines()),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "issues": issues,
                }
            except (OSError, RuntimeError, UnicodeError) as error:
                errors.append({"path": str(path), "error": str(error)})
                report["status"] = "error"
    names = {}
    for skill in skills.values():
        if skill["name"]:
            names.setdefault(skill["name"], []).append(skill["path"])
    return {
        "roots": root_reports,
        "skills": sorted(skills.values(), key=lambda skill: skill["path"]),
        "duplicate_names": {name: paths for name, paths in sorted(names.items()) if len(paths) > 1},
        "errors": errors,
    }


def default_roots():
    home, project = Path.home(), Path.cwd()
    return [
        home / ".agents/skills",
        home / ".pi/agent/skills",
        home / ".claude/skills",
        home / ".codex/skills",
        project / ".agents/skills",
        project / ".pi/skills",
        project / ".claude/skills",
        project / ".codex/skills",
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots", nargs="*", type=Path, help="Replace the default global/project roots"
    )
    args = parser.parse_args()
    roots = list(
        dict.fromkeys(path.expanduser().absolute() for path in (args.roots or default_roots()))
    )
    result = inventory(roots)
    print(json.dumps(result, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
