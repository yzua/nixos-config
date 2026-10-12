"""Enable Wine fullscreen mouse confinement in existing Steam game prefixes."""

import argparse
import os
import re
import shutil
import tempfile
from pathlib import Path

SECTION = r"[Software\\Wine\\X11 Driver]"
VALUE = '"GrabFullscreen"="Y"'


def enable_grab(text):
    """Preserve other registry settings and make this edit idempotent."""
    lines = text.splitlines(keepends=True)
    start = next(
        (i for i, line in enumerate(lines) if line.rstrip().split("]", 1)[0] + "]" == SECTION),
        None,
    )
    if start is None:
        return text.rstrip("\n") + f"\n\n{SECTION}\n{VALUE}\n"
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("[")),
        len(lines),
    )
    for i in range(start + 1, end):
        if re.match(r'"GrabFullscreen"\s*=', lines[i]):
            lines[i] = VALUE + "\n"
            return "".join(lines)
    lines.insert(start + 1, VALUE + "\n")
    return "".join(lines)


def steam_libraries(roots):
    libraries = set()
    for root in roots:
        root = root.expanduser().resolve()
        if not root.is_dir():
            continue
        libraries.add(root)
        manifest = root / "steamapps/libraryfolders.vdf"
        if manifest.is_file():
            for path in re.findall(r'"path"\s+"((?:\\.|[^"\\])*)"', manifest.read_text()):
                libraries.add(Path(path.replace(r"\\", "\\").replace(r"\"", '"')))
    return sorted(libraries)


def wine_running(proc=Path("/proc")):
    """Offline registry edits are unsafe while a Wine server can write them."""
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if (entry / "comm").read_text().strip().startswith("wineserver"):
                return True
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            # Cannot prove it is safe to edit another process's prefix.
            return True
    return False


def apply_registry(path):
    if path.is_symlink() or path.stat().st_uid != os.getuid():
        raise ValueError(f"Refusing non-owned or symlink registry: {path}")
    original = path.read_text()
    updated = enable_grab(original)
    if updated == original:
        return False
    backup = path.with_name(path.name + ".before-mouse-grab")
    # Never overwrite a previous recovery copy, or follow an existing symlink.
    try:
        with backup.open("x") as handle:
            handle.write(original)
        shutil.copymode(path, backup)
    except FileExistsError:
        pass
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        shutil.copymode(path, temporary)
        if path.read_text() != original or wine_running():
            raise ValueError(f"Registry changed or Wine started; not replacing {path}")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steam-root", type=Path, action="append", help="Additional Steam root")
    args = parser.parse_args()
    if wine_running():
        parser.exit(1, "Close all Proton/Wine games before running steam-mouse-grab.\n")
    home = Path.home()
    roots = [
        home / ".local/share/Steam",
        home / ".steam/steam",
        home / ".steam/root",
    ] + (args.steam_root or [])
    count = 0
    for library in steam_libraries(roots):
        for path in sorted((library / "steamapps/compatdata").glob("*/pfx/user.reg")):
            if not path.parent.parent.name.isdigit() or path.parent.parent.name == "0":
                continue
            if apply_registry(path):
                print(f"Enabled fullscreen mouse capture: {path.parent.parent.name}")
                count += 1
    print(f"Updated {count} game prefixes. Run again after new games create their prefixes.")


if __name__ == "__main__":
    main()
