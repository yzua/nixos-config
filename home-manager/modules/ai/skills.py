#!/usr/bin/env python3
"""Prepare pinned skill sources and install local, writable copies with skills.sh."""

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

UI_SEARCH_COMMAND = 'python "${CLAUDE_PLUGIN_ROOT}/.claude/skills/ui-ux-pro-max/scripts/search.py"'


def validate_source(path):
    if not path.is_dir() or not any(path.rglob("SKILL.md")):
        raise ValueError(f"Skill source contains no SKILL.md: {path}")


def repair_ui_search(source):
    skill = source / "ui-ux-pro-max/SKILL.md"
    search = skill.parent / "scripts/search.py"
    if not search.is_file():
        raise ValueError("UI/UX search script is missing")
    text = skill.read_text()
    if UI_SEARCH_COMMAND not in text:
        raise ValueError("UI/UX search command changed upstream; review its script path")
    # Resolve the installed shared copy at execution time, never the build/staging path.
    command = f'{sys.executable} -B "${{HOME}}/.agents/skills/ui-ux-pro-max/scripts/search.py"'
    skill.chmod(skill.stat().st_mode | stat.S_IWUSR)
    skill.write_text(text.replace(UI_SEARCH_COMMAND, command))


def prepare(manifest, output):
    sources = json.loads(manifest.read_text())
    if not isinstance(sources, list) or not sources:
        raise ValueError("Expected a nonempty skill source list")
    for source in sources:
        validate_source(Path(source["path"]))
    output.mkdir(parents=True)
    prepared = []
    for index, source in enumerate(sources):
        directory = f"source-{index}"
        target = output / directory
        shutil.copytree(source["path"], target)
        if source.get("repairUiSearch", False):
            repair_ui_search(target)
        prepared.append({"directory": directory, "skill": source["skill"], "url": source["url"]})
    (output / "manifest.json").write_text(json.dumps(prepared, indent=2) + "\n")


def install(bundle, cli):
    if "DRY_RUN" in os.environ:
        print("Would sync prepared pinned skills.sh sources for all agents")
        return
    sources = json.loads((bundle / "manifest.json").read_text())
    if not isinstance(sources, list) or not sources:
        raise ValueError("Expected a nonempty prepared skill source list")
    # Validate and stage the entire bundle before letting the installer touch HOME.
    with tempfile.TemporaryDirectory(prefix="agent-skills-") as temporary:
        staged = []
        for source in sources:
            directory = source["directory"]
            if (
                not isinstance(directory, str)
                or directory in {"", ".", ".."}
                or Path(directory).name != directory
            ):
                raise ValueError("Prepared skill directory must be a single path segment")
            path = bundle / directory
            validate_source(path)
            target = Path(temporary) / directory
            shutil.copytree(path, target)
            # skills.sh preserves source permissions; Nix store modes must not make
            # the installed copies read-only. Do not change the immutable bundle.
            for entry in [target, *target.rglob("*")]:
                entry.chmod(entry.stat().st_mode | stat.S_IWUSR)
            staged.append((target, source["skill"]))
        for path, skill in staged:
            subprocess.run(
                [str(cli), "add", str(path), "--global", "--agent", "*", "--skill", skill, "--yes"],
                check=True,
            )
    # Local global installs do not refresh skills.sh's remote lock entries.
    # The prepared manifest and Nix source hashes are authoritative provenance.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preparation = commands.add_parser("prepare")
    preparation.add_argument("manifest", type=Path)
    preparation.add_argument("output", type=Path)
    installation = commands.add_parser("install")
    installation.add_argument("bundle", type=Path)
    installation.add_argument("cli", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.manifest, args.output)
    else:
        install(args.bundle, args.cli)


if __name__ == "__main__":
    main()
