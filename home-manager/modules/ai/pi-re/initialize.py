#!/usr/bin/env python3
"""Archive legacy RE copies once; use the canonical live Pi configuration thereafter."""

import argparse
import contextlib
import copy
import fcntl
import json
import os
import stat
import tempfile
import time
from pathlib import Path

FILES = ("settings.json", "models.json", "auth.json")


def reject_symlinks(path):
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError("RE paths must not contain symlinks")


def private_directory(path):
    reject_symlinks(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.stat().st_uid != os.getuid():
        raise ValueError("RE state must belong to the caller")
    os.chmod(path, 0o700)


def regular(path):
    reject_symlinks(path)
    if path.exists():
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise ValueError("Private configuration must be caller-owned single-link regular files")


def read_object(path):
    regular(path)
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except (ValueError, OSError) as error:
        raise ValueError(f"Invalid private configuration: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Private configuration must be an object: {path.name}")
    return value


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_private(path, value):
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def legacy_process_running(agent_dir):
    """Best-effort Linux guard; inspect only for an exact legacy profile environment entry."""
    expected = b"PI_CODING_AGENT_DIR=" + os.fsencode(agent_dir)
    for process in Path("/proc").iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        try:
            if process.stat().st_uid == os.getuid():
                if expected in (process / "environ").read_bytes().split(b"\0"):
                    return True
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return False


def mutex_identity(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or any(path.iterdir()):
        raise ValueError("Preserve unsafe or nonempty legacy configuration mutexes for review")
    return (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns)


@contextlib.contextmanager
def native_file_locks(agent_dir):
    """Native lexical mutexes; initializer flock also excludes live migration writers."""
    held = []
    try:
        for name in FILES:
            path = agent_dir / f"{name}.lock"
            try:
                path.mkdir(mode=0o700)
            except FileExistsError as error:
                identity = mutex_identity(path)
                # Native async auth uses a 30s stale period (longest native lock period).
                # Recover crash leftovers only after that delay and with no observed
                # legacy writer. /proc is best-effort, not a lifetime exclusion lease.
                if time.time_ns() - identity[2] <= 30_000_000_000 or legacy_process_running(
                    agent_dir
                ):
                    raise ValueError(
                        "Pi configuration is busy; let active writes finish and retry (stale recovery after 30 seconds)"
                    ) from error
                if mutex_identity(path) != identity or legacy_process_running(agent_dir):
                    raise ValueError("Legacy configuration mutex changed; preserve it for review")
                path.rmdir()
                path.mkdir(mode=0o700)  # A replacement race aborts; never delete/retry it.
            held.append((path, mutex_identity(path)))
        yield
    finally:
        for path, identity in reversed(held):
            if mutex_identity(path) != identity:
                raise ValueError("Migration mutex ownership changed; preserve the replacement")
            path.rmdir()


def compatible_additions(models, auth, legacy_models, legacy_auth, default_provider):
    """Keep live values; import only missing entries with compatible provider routing."""
    result_models, result_auth = copy.deepcopy(models), copy.deepcopy(auth)
    providers = result_models.get("providers", {})
    old_providers = legacy_models.get("providers", {})
    if not isinstance(providers, dict):
        raise ValueError(
            "Shared model provider map must be an object; originals preserved for review"
        )
    compatible, conflicts = set(), set()
    counts = {"providers": 0, "models": 0, "logins": 0}
    if not isinstance(old_providers, dict):
        return result_models, result_auth, counts
    for name, previous in old_providers.items():
        if not isinstance(previous, dict):
            conflicts.add(name)
            continue
        if not isinstance(previous.get("models", []), list):
            conflicts.add(name)
            continue
        if name not in providers:
            # An existing login/default can refer to an implicit built-in provider.
            # Do not redirect it to a legacy custom endpoint just because no override exists.
            if name in auth or name == default_provider:
                conflicts.add(name)
                continue
            providers[name] = copy.deepcopy(previous)
            result_models["providers"] = providers
            counts["providers"] += 1
            counts["models"] += len(previous.get("models", []))
            compatible.add(name)
            continue
        current = providers[name]
        if not isinstance(current, dict) or {k: v for k, v in current.items() if k != "models"} != {
            k: v for k, v in previous.items() if k != "models"
        }:
            conflicts.add(name)
            continue
        existing, incoming = current.get("models", []), previous.get("models", [])
        if not isinstance(existing, list) or not isinstance(incoming, list):
            conflicts.add(name)
            continue
        identifiers = {entry.get("id") for entry in existing if isinstance(entry, dict)}
        additions = []
        for entry in incoming:
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("id"), str)
                and entry["id"] not in identifiers
            ):
                additions.append(entry)
                identifiers.add(entry["id"])
        if additions:
            current["models"] = existing + copy.deepcopy(additions)
            counts["models"] += len(additions)
        compatible.add(name)
    for name, credential in legacy_auth.items():
        if (
            name in result_auth
            or name in conflicts
            or (name in providers and name not in compatible)
        ):
            continue
        if not isinstance(credential, dict):
            continue
        api_key = credential.get("type") == "api_key" and isinstance(credential.get("key"), str)
        oauth = (
            credential.get("type") == "oauth"
            and all(isinstance(credential.get(key), str) for key in ("access", "refresh"))
            and isinstance(credential.get("expires"), (int, float))
        )
        if api_key or oauth:
            result_auth[name] = copy.deepcopy(credential)
            counts["logins"] += 1
    return result_models, result_auth, counts


def merge_missing_configuration(source_dir, backup):
    with native_file_locks(source_dir):
        settings, models, auth = (read_object(source_dir / name) for name in FILES)
        merged_models, merged_auth, counts = compatible_additions(
            models,
            auth,
            read_object(backup / "models.json"),
            read_object(backup / "auth.json"),
            settings.get("defaultProvider"),
        )
        # Models first makes crash recovery idempotent: a newly added provider must
        # exist before its login, rather than looking like an existing implicit provider.
        for name, before, after in (
            ("models.json", models, merged_models),
            ("auth.json", auth, merged_auth),
        ):
            if after != before:
                write_private(source_dir / name, after)
        return counts


def initialize(agent_dir, state_dir, source_dir):
    # Keep this legacy argument name for the init CLI; it is now the live shared directory.
    reject_symlinks(source_dir)
    source = source_dir.resolve()
    for destination in (agent_dir, state_dir):
        resolved = destination.resolve()
        if resolved.is_relative_to(source) or source.is_relative_to(resolved):
            raise ValueError("Legacy RE state and the shared agent directory must not overlap")
    private_directory(state_dir)
    private_directory(agent_dir)
    lock_path = state_dir / "initialize.lock"
    regular(lock_path)
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(descriptor, "a") as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ValueError("Initialization lock must be a regular file")
        os.fchmod(lock.fileno(), 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another RE initialization holds the lock") from error
        marker = state_dir / "shared-config-v1.json"
        regular(marker)
        # Normal launches validate paths, not credential contents concurrently being refreshed.
        for name in FILES:
            regular(source_dir / name)
            regular(agent_dir / name)
        if marker.exists():
            if read_object(marker).get("agentDir") != str(source_dir):
                raise ValueError("Shared Pi configuration location changed; review the migration")
            if any((agent_dir / name).exists() for name in FILES):
                raise ValueError(
                    "Legacy RE configuration reappeared after migration; preserve and review it"
                )
            return
        # Archive on the legacy filesystem: atomic rename preserves the original inode,
        # including an update through an already-open descriptor. No copy/unlink window,
        # truncated archive, cross-filesystem rename, or overwrite of previous backups.
        backup = agent_dir.parent / "backups" / "shared-config-v1"
        private_directory(backup)
        private_directory(source_dir)
        sync_directory(backup.parent)
        sync_directory(backup.parent.parent)
        with native_file_locks(agent_dir):
            if legacy_process_running(agent_dir):
                raise ValueError(
                    "Close all legacy RE sessions before migrating to shared Pi configuration"
                )
            for name in FILES:
                read_object(agent_dir / name)
                read_object(backup / name)
                if (agent_dir / name).exists() and (backup / name).exists():
                    raise ValueError(
                        "Legacy RE files reappeared during migration; close old sessions and review both copies"
                    )
            for name in FILES:
                original, archived = agent_dir / name, backup / name
                if original.exists():
                    os.chmod(original, 0o600)
                    with original.open("rb") as stream:
                        os.fsync(stream.fileno())
                    os.rename(original, archived)
            sync_directory(backup)
            sync_directory(agent_dir)
            if any((agent_dir / name).exists() for name in FILES):
                raise ValueError("Legacy RE files reappeared during migration; close old sessions")
            merged = merge_missing_configuration(source_dir, backup)
            write_private(
                marker,
                {
                    "version": 1,
                    "credentialMode": "shared",
                    "agentDir": str(source_dir),
                    "backup": str(backup),
                    "mergePolicy": "missing-compatible-only",
                    "mergedEntries": merged,
                },
            )
        print(
            f"RE now uses the live Pi login/models/settings. Legacy RE files archived privately in {backup}."
        )
        print(
            "Compatible RE-only providers/models/logins were merged; current Pi defaults and conflicts were kept."
        )


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
