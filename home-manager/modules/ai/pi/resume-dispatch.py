#!/usr/bin/env python3
"""Keep explicit RE root-session resumes in their reviewed profile, including Herdr restore."""

import os
import sys
from pathlib import Path

# Built-in Pi options whose next token is a value, not another option. The
# dispatcher never parses prompt text after --, nor changes ordinary Pi argv.
VALUE_FLAGS = {
    "--provider",
    "--model",
    "--api-key",
    "--thinking",
    "--models",
    "--mode",
    "--session",
    "--session-id",
    "--fork",
    "--session-dir",
    "--name",
    "-n",
    "--tools",
    "-t",
    "--exclude-tools",
    "-xt",
    "--extension",
    "-e",
    "--skill",
    "--prompt-template",
    "--theme",
    "--use-theme",
    "--system-prompt",
    "--append-system-prompt",
    "--tui-mode",
}


def option_indices(args):
    index = 0
    while index < len(args) and args[index] != "--":
        yield index
        index += 2 if args[index] in VALUE_FLAGS else 1


def session_argument(args):
    if args and args[0] in {
        "install",
        "remove",
        "uninstall",
        "update",
        "list",
        "config",
        "auth",
        "mcp",
    }:
        return None  # Package/auth commands are not interactive session launches.
    session = None
    for index in option_indices(args):
        if args[index] == "--export":
            return None
        if args[index] in {"--session", "--fork"} and index + 1 < len(args):
            session = args[index + 1]
    return session


def target(args, environment):
    session = session_argument(args)
    if session is None:
        return "pi"
    # Pi treats bare selectors as IDs, not cwd-relative paths. Do not hijack
    # coding ID lookup just because the caller is inspecting an RE directory.
    if "/" not in session and "\\" not in session and not session.endswith(".jsonl"):
        return "pi"
    home = Path(environment["HOME"])
    state = Path(environment.get("XDG_STATE_HOME") or home / ".local/state")
    if not home.is_absolute() or not state.is_absolute():
        raise ValueError("HOME and XDG_STATE_HOME must be absolute for session resume")
    re_state = state / "pi-re"
    candidate = Path(os.path.abspath(Path(session).expanduser()))
    canonical = candidate.resolve()

    def beneath(directory):
        # Lexical membership also routes missing/escaping RE symlinks to the
        # guarded RE launcher rather than accidentally opening them as coding Pi.
        return candidate.is_relative_to(directory) or canonical.is_relative_to(directory.resolve())

    if beneath(re_state / "subagents"):
        raise ValueError(
            "Headless RE Flash jobs are not interactive root sessions; use re_subagent for a new task"
        )
    return "pi-re" if beneath(re_state / "sessions") else "pi"


def main():
    # The managed wrapper supplies the pinned real Pi, so neither branch recurses.
    real_pi, separator, *args = sys.argv[1:]
    if separator != "--" or not Path(real_pi).is_absolute():
        raise ValueError("Expected an absolute real Pi executable and --")
    if target(args, os.environ) == "pi-re":
        # `p` supplies --approve for coding projects. A resumed RE root must
        # keep its unconditional --no-approve policy, not fail on that alias.
        approval = {index for index in option_indices(args) if args[index] in {"--approve", "-a"}}
        routed = [arg for index, arg in enumerate(args) if index not in approval]
        os.execvp("pi-re", ["pi-re", *routed])
    os.execv(real_pi, [real_pi, *args])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"pi resume: {error}", file=sys.stderr)
        sys.exit(1)
