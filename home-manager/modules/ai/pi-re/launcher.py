#!/usr/bin/env python3
"""Launch the reviewed RE profile or its explicitly selected lab operations."""

import contextlib
import json
import os
import re
import stat
import sys
from pathlib import Path

from initialize import initialize

SKILLS = (
    "re-intake",
    "android-static",
    "android-runtime",
    "web-protocol",
    "native-analysis",
    "finding-validation",
    "adapter-build",
    "re-browser",
    "re-device",
    "rea-analysis",
)
VALUE_FLAGS = {"--model", "--provider", "--thinking", "--mode", "--session"}
BOOL_FLAGS = {"--print", "-p", "--continue", "-c", "--resume", "-r", "--verbose"}


def paths(environment=None):
    environment = os.environ if environment is None else environment
    home = Path(environment["HOME"])
    data = Path(environment.get("XDG_DATA_HOME") or home / ".local/share") / "pi-re"
    state = Path(environment.get("XDG_STATE_HOME") or home / ".local/state") / "pi-re"
    if not data.is_absolute() or not state.is_absolute():
        raise ValueError("XDG RE paths must be absolute")
    return {"agent": data / "agent", "state": state, "sessions": state / "sessions"}


def child_sessions(locations, environment=None):
    environment = os.environ if environment is None else environment
    override = environment.get("PI_RE_CHILD_SESSION_DIR")
    if not override:
        return
    if environment.get("PI_RE_CHILD") != "1":
        raise ValueError("Child session override is restricted to RE children")
    directory = Path(override)
    root = locations["state"] / "subagents" / "jobs"
    if (
        not directory.is_absolute()
        or ".." in directory.parts
        or directory.name != "sessions"
        or directory.parent.parent != root
        or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", directory.parent.name)
    ):
        raise ValueError("Invalid private RE child session location")
    for component in (*reversed(directory.parents), directory):
        if component.is_symlink():
            raise ValueError("Child session path must not contain symlinks")
        if component == locations["state"] or component.is_relative_to(locations["state"]):
            info = component.stat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError("Child session directories must be private and caller-owned")
    locations["sessions"] = directory


def checked_args(args, session_dir):
    result = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            return result + args[index:]
        if not arg.startswith("-"):
            result.append(arg)
        elif arg in BOOL_FLAGS:
            result.append(arg)
        elif arg in VALUE_FLAGS:
            index += 1
            if index == len(args):
                raise ValueError(f"Missing value for {arg}")
            value = args[index]
            if arg == "--mode" and value not in ("text", "json"):
                raise ValueError("RE supports interactive/text/JSON mode, not RPC mode")
            if arg == "--session":
                candidate = Path(value).expanduser()
                if candidate.is_symlink() or not candidate.is_file():
                    raise ValueError("Select an existing RE session file")
                candidate = candidate.resolve()
                if not candidate.is_relative_to(session_dir.resolve()):
                    raise ValueError("Foreign sessions cannot be opened in the RE profile")
                value = str(candidate)
            result.extend((arg, value))
        else:
            raise ValueError(f"Unsupported RE argument: {arg}; use -- before prompt text")
        index += 1
    return result


def pi_arguments(config, locations, args):
    resources = Path(config["resources"])
    result = [
        config["pi"],
        "--no-approve",
        "--no-context-files",
        "--no-skills",
        "--no-extensions",
        "--no-prompt-templates",
        "--no-themes",
        "--offline",
        "--session-dir",
        str(locations["sessions"]),
        "--append-system-prompt",
        str(resources / "contract.md"),
    ]
    for skill in SKILLS:
        path = resources / "skills" / skill
        if not (path / "SKILL.md").is_file():
            raise ValueError(f"Reviewed skill is missing: {skill}")
        result.extend(("--skill", str(path)))
    result.extend(("--prompt-template", str(resources / "prompts")))
    if os.environ.get("PI_RE_CHILD") != "1":
        # Share only reviewed root question/reporting resources, not ambient
        # coding extensions. Headless Flash children retain no extensions.
        for extension in (
            resources / "flash-subagent.ts",
            Path(config["herdrIntegration"]),
            Path(config["questionExtension"]),
        ):
            if not extension.is_absolute() or not extension.is_file():
                raise ValueError(f"Reviewed root extension is missing: {extension}")
            result.extend(("--extension", str(extension)))
    return result + checked_args(args, locations["sessions"])


def doctor(config, locations, as_json):
    capabilities = []
    for item in config["capabilities"]:
        tools = item.get("tools", {})
        artifacts = item.get("artifacts", {})
        installed = (
            bool(tools)
            and all(os.access(path, os.X_OK) for path in tools.values())
            and all(Path(path).is_file() for path in artifacts.values())
        )
        capabilities.append(
            {
                "id": item["id"],
                "skill": item["skill"],
                "versions": item.get("versions", {}),
                "availability": "installed-unqualified" if installed else "unavailable",
                "enabled": installed,
                "qualified": False,
                "compatibility": "pending-agent-trials" if installed else "unavailable",
            }
        )
    result = {
        "status": "ok",
        "executionMode": "host-not-sandbox",
        "profileInitialized": (locations["state"] / "initialized-v1.json").is_file(),
        "rootRequired": True,
        "runtimeQualification": "pending agent trials; android status is process-only",
        "capabilities": capabilities,
    }
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print("pi-re: host mode (not a sandbox); rooted Android is mandatory for Frida.")
        print("Profile initialized:", result["profileInitialized"])
        for item in capabilities:
            print(f"  {item['id']}: {item['availability']} — skill {item['skill']}")
        print("Device/agent ability qualification is separate; doctor performs no live probes.")


def main():
    config = json.loads(Path(os.environ["PI_RE_CONFIG"]).read_text())
    locations = paths()
    child_sessions(locations)
    args = sys.argv[1:]
    if args and args[0] in ("help", "--help", "-h"):
        print(
            "pi-re [Pi prompt/options]\n"
            "pi-re init | doctor [--json]\n"
            "pi-re rea <static command> [args] (pinned Ghidra/JADX/JavaScript analysis)\n"
            "pi-re android create|start|status|root|stop|reset [--json] [--visible]\n"
            "pi-re device <agent-device command>\n"
            "pi-re frida setup|status|stop|run [options]\n"
            "pi-re lab start [--allow-host NAME] [--visible] | status | stop | check [--json]\n"
            "Pi options: --model, --provider, --thinking, --print, --mode text|json, "
            "--continue, --resume, --session <RE file>.\n"
            "Host mode is autonomous, not a sandbox; use owned/authorized targets."
        )
        return
    if args and args[0] == "doctor":
        if args[1:] not in ([], ["--json"]):
            raise ValueError("doctor accepts only --json; it never installs or probes devices")
        doctor(config, locations, "--json" in args)
        return
    if args and args[0] == "init":
        if len(args) != 1:
            raise ValueError("init takes no arguments")
        initialize(locations["agent"], locations["state"], Path(config["sourceAgentDir"]))
        return
    if args and args[0] == "rea":
        from rea import command as rea_command

        command, environment = rea_command(config, locations, args[1:])
        os.execve(command[0], command, environment)
    if args and args[0] in ("android", "device", "frida", "lab"):
        script = {"android": "android.py", "lab": "lab.py"}.get(args[0], "runtime.py")
        command = args[1:] if args[0] in ("android", "lab") else args
        os.execv(
            config["python"],
            [
                config["python"],
                str(Path(__file__).parent / script),
                "--config",
                os.environ["PI_RE_CONFIG"],
                "--state-dir",
                str(locations["state"]),
                *command,
            ],
        )
    # Validate user flags and all resources before initializing or starting a provider.
    command = pi_arguments(config, locations, args)
    with contextlib.redirect_stdout(sys.stderr):
        initialize(locations["agent"], locations["state"], Path(config["sourceAgentDir"]))
    locations["sessions"].mkdir(parents=True, exist_ok=True, mode=0o700)
    if locations["sessions"].is_symlink():
        raise ValueError("RE sessions must not be a symlink")
    os.environ["PI_CODING_AGENT_DIR"] = str(locations["agent"])
    os.environ["PI_CODING_AGENT_SESSION_DIR"] = str(locations["sessions"])
    os.environ["PI_OFFLINE"] = "1"
    os.execv(config["pi"], command)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(f"pi-re: {error}", file=sys.stderr)
        sys.exit(1)
