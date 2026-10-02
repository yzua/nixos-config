#!/usr/bin/env python3
"""Initialize independent writable RE state without changing the coding profile."""

import argparse
import fcntl
import json
import os
import stat
import tempfile
from pathlib import Path

SETTING_KEYS = (
    "defaultProvider",
    "defaultModel",
    "defaultThinkingLevel",
    "modelThinkingLevels",
    "thinkingBudgets",
    "httpProxy",
)


def reject_symlinks(path):
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError("RE paths must not contain symlinks")


def private_directory(path):
    reject_symlinks(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_uid != os.getuid():
        raise ValueError("RE state must belong to the caller")
    os.chmod(path, 0o700)


def read_object(path):
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except (ValueError, OSError) as error:
        raise ValueError(f"Invalid private configuration: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Private configuration must be an object: {path.name}")
    return value


def write_private(path, value):
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def initialize(agent_dir, state_dir, source_dir):
    source = source_dir.resolve()
    for destination in (agent_dir, state_dir):
        resolved = destination.resolve()
        if resolved.is_relative_to(source) or source.is_relative_to(resolved):
            raise ValueError("RE and coding directories must not overlap")
    private_directory(state_dir)
    private_directory(agent_dir)
    lock_path = state_dir / "initialize.lock"
    if lock_path.is_symlink():
        raise ValueError("Initialization lock must not be a symlink")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(descriptor, "a") as lock:
        info = os.fstat(lock.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise ValueError("Initialization lock must be a caller-owned single-link regular file")
        os.fchmod(lock.fileno(), 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another RE initialization holds the lock") from error
        marker = state_dir / "initialized-v1.json"
        destinations = [agent_dir / name for name in ("settings.json", "models.json", "auth.json")]
        for path in (marker, *destinations):
            reject_symlinks(path)
            if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
                raise ValueError("RE configuration must be single-link regular files")
        if marker.exists():
            print("RE profile already initialized; preserving writable settings and login.")
            return
        # Validate all input before publishing any configuration. Never print its contents.
        settings = read_object(source_dir / "settings.json")
        models = read_object(source_dir / "models.json")
        auth = read_object(source_dir / "auth.json")
        desired = {key: settings[key] for key in SETTING_KEYS if key in settings}
        desired.update(
            defaultProjectTrust="never",
            extensions=["-builtin:mcp"],
            enableInstallTelemetry=False,
            enableAnalytics=False,
        )
        for path, value in zip(destinations, (desired, models, auth), strict=True):
            if path.exists():
                read_object(path)
                os.chmod(path, 0o600)
            else:
                write_private(path, value)
        write_private(marker, {"version": 1, "credentialMode": "independent-copy"})
        if any(isinstance(entry, dict) and entry.get("type") == "oauth" for entry in auth.values()):
            print("Copied OAuth login: refresh-token rotation may require a separate RE login.")
        print("Initialized separate RE profile. Coding configuration was not modified.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-dir", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--source-agent-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        initialize(args.agent_dir, args.state_dir, args.source_agent_dir)
    except (ValueError, OSError) as error:
        parser.exit(1, f"pi-re initialization failed: {error}\n")


if __name__ == "__main__":
    main()
