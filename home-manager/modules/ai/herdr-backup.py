#!/usr/bin/env python3
"""Keep bounded private recovery copies of valid Herdr layouts; never restore live state."""

import argparse
import errno
import fcntl
import json
import math
import os
import stat
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

MAX_LAYOUT_BYTES = 16 * 1024 * 1024


def reject_symlinks(path):
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError("Recovery paths must not contain symlinks")


def private_directory(path):
    reject_symlinks(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_uid != os.getuid():
        raise ValueError("Recovery directories must belong to the caller")
    path.chmod(0o700)


def read_regular(path):
    """Read one bounded stable inode; a missing/unsafe source is not recovery evidence."""
    try:
        reject_symlinks(path)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except ValueError:
        return None, False
    except OSError as error:
        if error.errno in (errno.ENOENT, errno.ELOOP, errno.ENXIO):
            return None, False
        raise
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_LAYOUT_BYTES:
            return None, False
        data = stream.read(MAX_LAYOUT_BYTES + 1)
        after = os.fstat(stream.fileno())
        if len(data) > MAX_LAYOUT_BYTES or (
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            return None, False
        private = (
            after.st_uid == os.getuid()
            and after.st_nlink == 1
            and stat.S_IMODE(after.st_mode) == 0o600
        )
        return data, private


def atomic_copy(path, data):
    descriptor, temporary = tempfile.mkstemp(prefix=".layout-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        Path(temporary).unlink(missing_ok=True)


def unsigned(value, maximum=0xFFFFFFFFFFFFFFFF):
    return type(value) is int and 0 <= value <= maximum


def pane_id(value):
    return unsigned(value, 0xFFFFFFFF)


def string(value):
    return isinstance(value, str)


def string_list(value):
    return isinstance(value, list) and all(string(item) for item in value)


def finite_float(value):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= 3.4028235e38


def metadata(owner, fields, nullable=()):
    """Check known serde fields; absent/defaulted and unknown additive fields stay compatible."""
    return all(
        key not in owner or (key in nullable and owner[key] is None) or check(owner[key])
        for key, check in fields.items()
    )


def public_pane_numbers(value):
    return isinstance(value, dict) and all(
        key.isascii() and key.isdigit() and pane_id(int(key)) and unsigned(number)
        for key, number in value.items()
    )


def worktree_space(value):
    return (
        isinstance(value, dict)
        and all(string(value.get(key)) for key in ("key", "label", "repo_root", "checkout_path"))
        and type(value.get("is_linked_worktree")) is bool
    )


def valid_tab(tab):
    if not isinstance(tab, dict) or type(tab.get("zoomed")) is not bool:
        return False
    if not metadata(tab, {"custom_name": string}, nullable=("custom_name",)):
        return False
    panes = tab.get("panes")
    if not isinstance(panes, dict) or not panes:
        return False
    for key, pane in panes.items():
        if not key.isascii() or not key.isdigit() or not pane_id(int(key)):
            return False
        if not isinstance(pane, dict) or not isinstance(pane.get("cwd"), str):
            return False
        for field in ("label", "agent_name", "managed_agent_kind"):
            if pane.get(field) is not None and not isinstance(pane[field], str):
                return False
        session = pane.get("agent_session")
        if session is not None and (
            not isinstance(session, dict)
            or not all(
                isinstance(session.get(field), str) for field in ("source", "agent", "value")
            )
            or session.get("kind") not in ("path", "id")
        ):
            return False
        for field in ("agent_resume", "launch_argv"):
            value = pane.get(field)
            if value is None:
                continue
            if field == "agent_resume":
                if not isinstance(value, dict) or not all(
                    isinstance(value.get(key), str) for key in ("source", "agent")
                ):
                    return False
                value = value.get("argv")
            if not isinstance(value, list) or not all(isinstance(arg, str) for arg in value):
                return False
    for field in ("focused", "root_pane"):
        value = tab.get(field)
        if value is not None and (not pane_id(value) or str(value) not in panes):
            return False
    # Validate the tagged BSP tree iteratively; bounded JSON is still untrusted.
    pending = [tab.get("layout")]
    seen = set()
    while pending:
        node = pending.pop()
        if not isinstance(node, dict) or len(node) != 1:
            return False
        if "Pane" in node:
            value = node["Pane"]
            if not pane_id(value) or str(value) not in panes or value in seen:
                return False
            seen.add(value)
        elif "Split" in node:
            split = node["Split"]
            if not isinstance(split, dict) or split.get("direction") not in (
                "Horizontal",
                "Vertical",
            ):
                return False
            ratio = split.get("ratio")
            if type(ratio) not in (int, float) or not math.isfinite(ratio) or not 0 < ratio < 1:
                return False
            pending.extend((split.get("first"), split.get("second")))
        else:
            return False
    return seen == {int(key) for key in panes}


def json_values_valid(value):
    """Match serde_json's UTF-8/finite-number contract, including unknown additive fields."""
    pending = [value]
    try:
        while pending:
            item = pending.pop()
            if isinstance(item, str):
                item.encode("utf-8")
            elif isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
            elif isinstance(item, float) and not math.isfinite(item):
                return False
        return True
    except UnicodeEncodeError:
        return False


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON field")
        value[key] = item
    return value


def invalid_constant(value):
    raise ValueError(f"Non-JSON numeric constant: {value}")


def valid_layout(data):
    """Validate recoverable v3 structure against Herdr v0.9.3 snapshot.rs."""
    try:
        layout = json.loads(data, object_pairs_hook=unique_object, parse_constant=invalid_constant)
        if not json_values_valid(layout):
            return False
        if (
            not isinstance(layout, dict)
            or type(layout.get("version")) is not int
            or layout["version"] != 3
        ):
            return False
        workspaces = layout.get("workspaces")
        if not isinstance(workspaces, list) or not workspaces:
            return False
        if not metadata(
            layout,
            {
                "selected": unsigned,
                "active": unsigned,
                "sidebar_width": lambda value: unsigned(value, 0xFFFF),
                "sidebar_section_split": finite_float,
                "collapsed_space_keys": string_list,
            },
            nullable=("active", "sidebar_width", "sidebar_section_split"),
        ):
            return False
        for workspace in workspaces:
            if not isinstance(workspace, dict) or not isinstance(
                workspace.get("identity_cwd"), str
            ):
                return False
            if not metadata(
                workspace,
                {
                    "id": string,
                    "custom_name": string,
                    "worktree_space": worktree_space,
                    "public_pane_numbers": public_pane_numbers,
                    "next_public_pane_number": unsigned,
                    "next_public_tab_number": unsigned,
                    "public_tab_numbers": lambda value: (
                        isinstance(value, list) and all(unsigned(item) for item in value)
                    ),
                },
                nullable=("id", "custom_name", "worktree_space"),
            ):
                return False
            tabs = workspace.get("tabs")
            if not isinstance(tabs, list) or not tabs or not all(valid_tab(tab) for tab in tabs):
                return False
            active_tab = workspace.get("active_tab", 0)
            if type(active_tab) is not int or not 0 <= active_tab < len(tabs):
                return False
        return True
    except (ValueError, UnicodeDecodeError, RecursionError, OverflowError):
        return False


def audit_history(folder):
    """Secure retained history even when its live session no longer exists."""
    private_directory(folder)
    retained = [folder / "latest.json"]
    for pattern, count in (("snapshot-*.json", 96), ("day-*.json", 8)):
        history = sorted(folder.glob(pattern))
        for obsolete in history[:-count]:
            obsolete.unlink()
        retained.extend(history[-count:])
    for path in retained:
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError("Recovery history must contain caller-owned regular files")
        if info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
            historical, _ = read_regular(path)
            if historical is None:
                raise ValueError("Unsafe recovery history could not be read within bounds")
            atomic_copy(path, historical)


def backup_layouts(config_dir, state_dir, now=None):
    now = now or datetime.now(UTC)
    private_directory(state_dir)
    lock_descriptor = os.open(
        state_dir / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600
    )
    with os.fdopen(lock_descriptor, "rb") as lock:
        info = os.fstat(lock.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise ValueError("Recovery lock must be a caller-owned regular file without aliases")
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for folder in sorted(state_dir.iterdir()):
            if folder.name == "default" or folder.name.startswith("named-"):
                audit_history(folder)
        sources = [("default", config_dir / "session.json")]
        named = config_dir / "sessions"
        if named.is_dir() and not named.is_symlink():
            sources.extend(
                ("named-" + directory.name, directory / "session.json")
                for directory in sorted(named.iterdir())
                if directory.is_dir() and not directory.is_symlink()
            )
        copied = 0
        for name, source in sources:
            data, _ = read_regular(source)
            if data is None or not valid_layout(data):
                continue  # Empty/corrupt shutdown state never replaces recovery data.
            folder = state_dir / name
            private_directory(folder)
            latest = folder / "latest.json"
            previous, private = read_regular(latest)
            changed = previous != data
            if changed:
                filename = "snapshot-" + now.strftime("%Y%m%dT%H%M%S%fZ") + ".json"
                atomic_copy(folder / filename, data)
                copied += 1
            if changed or not private:
                atomic_copy(latest, data)
            daily = folder / ("day-" + now.strftime("%Y-%m-%d") + ".json")
            previous_daily, private = read_regular(daily)
            if changed or previous_daily is None or not private:
                atomic_copy(daily, data)
            audit_history(folder)
        return copied


def check_server(binary):
    try:
        installed = subprocess.check_output([binary, "--version"], text=True, timeout=10).strip()
        status = subprocess.run(
            [binary, "status", "server"], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        print("WARNING: Herdr version readiness could not be checked; live sessions untouched.")
        return
    if status.returncode != 0:
        print("WARNING: Herdr server readiness could not be checked; live sessions untouched.")
        return
    values = dict(line.split(": ", 1) for line in status.stdout.splitlines() if ": " in line)
    expected = installed.removeprefix("herdr ")
    if values.get("status") == "running" and values.get("version") != expected:
        print(
            "WARNING: The selected Herdr server has not adopted the installed update. "
            "Before rebooting, save work and gracefully restart it from outside Herdr. "
            "Installing an update alone does not protect existing panes."
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", required=True, type=Path)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--check-server", type=str)
    arguments = parser.parse_args()
    count = backup_layouts(arguments.config_dir, arguments.state_dir)
    print(f"Herdr recovery: saved {count} changed layout(s); live sessions untouched.")
    if arguments.check_server:
        check_server(arguments.check_server)


if __name__ == "__main__":
    main()
