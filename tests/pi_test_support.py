"""Lazy resources and caller isolation for ordinary offline Pi regressions."""

import json
import os
import re
import shutil
from pathlib import Path


def pdf_fixture(padding=0):
    """Synthetic PDF shared by ordinary and RE profile loader fixtures."""
    content = b"BT /F1 16 Tf 72 720 Td (PI_PDF_MARKER: PDF extraction works.) Tj ET"
    content += b" " * padding
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    result = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(result)
    result += b"xref\n0 6\n0000000000 65535 f \n"
    result += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    result += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return result


def _direct_pi_behind_wrapper(executable: Path) -> str | None:
    """Resolve the pinned binary behind a managed resume-dispatch wrapper.

    The compatibility `pi` command dispatches through launcher scripts that
    normalize the environment for cross-profile safety. Direct-binary suites
    simulate explicit-load profiles themselves, so they need the real binary.
    """
    try:
        if executable.read_bytes()[:1] != b"#":
            return None  # Already the direct binary.
    except OSError:
        return None
    # The compatibility command may chain launcher scripts before the runtime
    # description appears; follow that chain for a bounded number of hops.
    scripts = [executable]
    try:
        scripts.append(Path(executable.resolve()))
        for _hop in range(3):
            text = "\n".join(path.read_text(errors="replace")[:4000] for path in scripts)
            match = re.search(r"(\S+-pi-coding-runtime\.json)", text)
            if match:
                config = json.loads(Path(match.group(1)).read_text())
                candidate = Path(config["pi"])
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return str(candidate)
            launch = re.search(r"(\S+-pi-coding-launch)\b", text)
            if not launch:
                break
            scripts.append(Path(launch.group(1)))
    except (OSError, ValueError, KeyError):
        pass
    return None


def require_pi() -> str:
    """Resolve the caller's Pi executable before changing fixture cwd or identity."""
    override = os.environ.get("PI_BIN")
    if override:
        executable = Path(override).absolute()
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise SystemExit(f"PI_BIN is not executable: {override}")
        return str(executable)
    executable = shutil.which("pi")
    if not executable:
        raise SystemExit(
            "Pi is required for loader regressions; install the managed profile or set PI_BIN."
        )
    resolved = Path(executable).absolute()
    return _direct_pi_behind_wrapper(resolved) or str(resolved)


def require_web_fetch_dependencies() -> Path:
    """Find managed dependencies, not source code, in the caller's installation."""
    override = os.environ.get("PI_WEB_FETCH_DIR")
    directory = (
        Path(override) if override is not None else Path.home() / ".pi/agent/extensions/web-fetch"
    )
    if not (directory / "node_modules").is_dir():
        raise SystemExit(
            "Managed web-fetch dependencies are required; set PI_WEB_FETCH_DIR to test another installation."
        )
    return directory.absolute()


def isolated_environment() -> dict[str, str]:
    """Copy the caller environment without live multiplexer or child identity.

    Suites must add their private fixture identity after isolation, and retain
    ownership of any fixture-specific exclusions (such as agent directories).
    Resource overrides, PATH and unrelated configuration are intentionally kept.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("HERDR_", "PI_SUBAGENT")) and key not in {"TMUX", "TMUX_PANE"}
    }


if __name__ == "__main__":
    # The aggregate runner shares exactly the same prerequisites as direct suites.
    require_pi()
    require_web_fetch_dependencies()
