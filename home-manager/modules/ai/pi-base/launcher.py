#!/usr/bin/env python3
"""Launch profiles with one canonical login/settings path and explicit domain loadouts."""

import json
import os
import sys
from pathlib import Path

VALUE_FLAGS = {"--model", "--provider", "--thinking", "--mode", "--session"}
BOOL_FLAGS = {"--print", "-p", "--continue", "-c", "--resume", "-r", "--verbose"}


def checked_args(args, sessions):
    result = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            return result + args[index:]
        if not arg.startswith("-") or arg in BOOL_FLAGS:
            result.append(arg)
        elif arg in VALUE_FLAGS:
            index += 1
            if index == len(args):
                raise ValueError(f"Missing value for {arg}")
            value = args[index]
            if arg == "--mode" and value not in ("text", "json"):
                raise ValueError("Explicit-load profiles support text/JSON mode, not RPC")
            if arg == "--session":
                path = Path(value).expanduser()
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Select an existing root session file")
                path = path.resolve()
                if not path.is_relative_to(sessions.resolve()):
                    raise ValueError("Foreign sessions require their own profile launcher")
                value = str(path)
            result.extend((arg, value))
        else:
            raise ValueError(f"Unsupported profile argument: {arg}; use -- before prompt text")
        index += 1
    return result


def pi_arguments(config, args):
    if config["profile"] == "pi-coding":
        return [config["pi"], *args]  # Native discovery, trust, sessions and full argv semantics.
    sessions = Path(config["sessions"])
    result = [
        config["pi"],
        "--no-approve",
        "--no-context-files",
        "--no-skills",
        "--no-extensions",
        "--no-prompt-templates",
        "--no-themes",
        "--offline",
        "--no-mcp",
        "--session-dir",
        str(sessions),
        "--tools",
        "read,bash,edit,write,ask_user_question,web_search,web_fetch,subagent,subagent_message,subagents_list",
    ]
    for extension in config["commonExtensions"]:
        path = Path(extension)
        if not path.is_absolute() or not path.exists():
            raise ValueError("An immutable base extension is missing")
        result.extend(("--extension", str(path)))
    for instructions in config["instructions"]:
        result.extend(("--append-system-prompt", str(instructions)))
    for skill in config["skills"]:
        result.extend(("--skill", str(skill)))
    return result + checked_args(args, sessions)


def private_session_directory(path):
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError("Profile session paths must not contain symlinks")
    for directory in (path.parent, path):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not directory.is_dir() or directory.stat().st_uid != os.getuid():
            raise ValueError("Profile sessions must belong to the caller")
        os.chmod(directory, 0o700)


def profile_environment(config, environment):
    result = dict(environment)
    previous = result.get("PI_PROFILE")
    state = Path(result.get("XDG_STATE_HOME") or Path(result["HOME"]) / ".local/state")
    inherited_sessions = result.get("PI_CODING_AGENT_SESSION_DIR")
    re_sessions = inherited_sessions and Path(inherited_sessions).is_relative_to(state / "pi-re")
    if previous in ("pi-re", "pi-home", "pi-base") or re_sessions:
        result.pop("PI_CODING_AGENT_SESSION_DIR", None)
        result.pop("PI_OFFLINE", None)
    # Domain helper identity must not survive a transition to coding/base/personal.
    for key in list(result):
        if key.startswith("PI_RE_"):
            del result[key]
    agent = config["agentDir"]
    if (
        config["profile"] == "pi-coding"
        and previous not in ("pi-re", "pi-home", "pi-base")
        and not re_sessions
        and "PI_RE_CONFIG" not in environment
    ):
        # Preserve deliberate native coding/role-profile overrides, including test fixtures.
        agent = environment.get("PI_CODING_AGENT_DIR") or agent
    result["PI_CODING_AGENT_DIR"] = agent
    result["PI_PROFILE"] = config["profile"]
    result.pop("PI_BASE_CHILD_POLICY", None)
    if config["profile"] != "pi-coding":
        result["PI_BASE_CHILD_POLICY"] = json.dumps(
            {
                "profile": config["profile"],
                "pi": config["pi"],
                "agentDir": agent,
                "sessions": str(Path(config["sessions"]).parent / "interactive-subagents/sessions"),
                "instructions": config["instructions"],
                "skills": config["skills"],
                "extensions": config["commonExtensions"],
            }
        )
    return result


def main():
    config = json.loads(Path(sys.argv[1]).read_text())
    home = Path(os.environ["HOME"])
    state = Path(os.environ.get("XDG_STATE_HOME") or home / ".local/state")
    if not home.is_absolute() or not state.is_absolute():
        raise ValueError("HOME and XDG_STATE_HOME must be absolute")
    config["agentDir"] = str(home / config["agentDir"])
    if "sessions" in config:
        config["sessions"] = str(state / config["sessions"])
    args = sys.argv[2:]
    if config["profile"] == "pi-home" and args[:1] == ["tv"]:
        os.execv(
            config["tvPython"],
            [config["tvPython"], config["tvScript"], config["tvConfig"], *args[1:]],
        )
    if config["profile"] != "pi-coding":
        if args[:1] in (["--help"], ["-h"], ["help"]):
            print(
                f"{config['profile']} [prompt] [--model MODEL] [--provider PROVIDER] "
                "[--thinking LEVEL] [--print] [--mode text|json] [--continue|--resume] "
                "[--session FILE]\nShared login/settings; separate sessions; explicit base resources."
            )
            if config["profile"] == "pi-home":
                print("pi-home tv --help  (on-demand Samsung control; no startup connection)")
            return
        os.umask(0o077)
        sessions = Path(config["sessions"])
        private_session_directory(sessions)
    # Identical lexical paths also mean identical native auth/settings lock paths.
    environment = profile_environment(config, os.environ)
    command = pi_arguments(config, args)
    os.execve(command[0], command, environment)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"Pi profile: {error}", file=sys.stderr)
        sys.exit(1)
