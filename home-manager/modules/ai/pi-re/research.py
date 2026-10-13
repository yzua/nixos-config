#!/usr/bin/env python3
"""Parent-scoped, resumable read-only research turns; not a host sandbox."""

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

from initialize import write_private
from subagent import (
    LOG_BYTES,
    MODEL,
    PROMPT_BYTES,
    PROVIDER,
    STDERR_BYTES,
    Events,
    bounded_summary,
    caller_paths,
    child_environment,
    child_running,
    die_with_helper,
    no_symlinks,
    open_private,
    private_directory,
    validate_sessions,
)

NAME = re.compile(r"[a-z][a-z0-9_-]{0,47}")
SESSION_BYTES = 16 * 1024 * 1024


def policy(config):
    value = config.get("research", {})
    result = {
        "maxConcurrent": value.get("maxConcurrent", 4),
        "defaultTimeoutSeconds": value.get("defaultTimeoutSeconds", 600),
        "maxTimeoutSeconds": value.get("maxTimeoutSeconds", 1800),
    }
    if any(type(number) is not int for number in result.values()):
        raise ValueError("Research policy requires integer budgets")
    if not 1 <= result["maxConcurrent"] <= 4:
        raise ValueError("Research concurrency must be between one and four")
    if not 1 <= result["defaultTimeoutSeconds"] <= result["maxTimeoutSeconds"] <= 3600:
        raise ValueError("Research timeouts must be finite, ordered and at most 3600 seconds")
    return result


def process_identity(pid):
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
        fields = text[text.rfind(")") + 2 :].split()
        if fields[0] in ("Z", "X"):
            return None  # Exited/zombie processes cannot retain a native-session writer.
        return {
            "pid": pid,
            "start": fields[19],
            "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        }
    except FileNotFoundError:
        return None


def parent_key(state, parent):
    no_symlinks(parent)
    if parent.parent != state / "sessions" or not parent.is_file():
        raise ValueError("Research requires an existing root RE session")
    private_directory(state / "sessions")
    # Older native root sessions may be 0644 inside a private 0700 directory.
    # Validate ownership without changing a live transcript or rejecting safe legacy roots.
    descriptor = os.open(parent, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info, entry = os.fstat(descriptor), parent.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or (info.st_dev, info.st_ino) != (entry.st_dev, entry.st_ino)
        ):
            raise ValueError("Research parent must be an owned single-link native root session")
    finally:
        os.close(descriptor)
    return hashlib.sha256(str(parent).encode()).hexdigest()


@contextlib.contextmanager
def exclusive(path, message):
    with open_private(path) as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError(message) from error
        yield lock


@contextlib.contextmanager
def slot(root, count):
    for number in range(count):
        with open_private(root / f"slot-{number}.lock") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            yield lock
            return
    raise ValueError(f"At most {count} research workers may run concurrently")


def read_metadata(path):
    with open_private(path) as stream:
        raw = stream.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024:
        raise ValueError("Research metadata exceeds its budget")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Invalid research metadata")
    return value


def validate_resume(metadata, fingerprint, cwd, sessions):
    if metadata.get("version") != 1 or metadata.get("config") != fingerprint:
        raise ValueError("Research loadout changed; start a new named worker")
    if metadata.get("cwd") != str(cwd) or metadata.get("phase") not in ("finished", "running"):
        raise ValueError("Unknown research writer ownership; resume blocked")
    writer = metadata.get("writer")
    if metadata["phase"] == "running":
        if (
            not isinstance(writer, dict)
            or set(writer) != {"pid", "start", "boot"}
            or type(writer.get("pid")) is not int
            or writer["pid"] <= 0
            or not isinstance(writer.get("start"), str)
            or not writer["start"].isdigit()
            or not isinstance(writer.get("boot"), str)
            or not writer["boot"]
        ):
            raise ValueError("Unknown research writer ownership; resume blocked")
        if process_identity(writer["pid"]) == writer:
            raise ValueError("The previous research writer is still alive")
    # A helper can die after Pi created the allocated native session but before
    # publishing its filename. Recover only one private file with that exact UUID.
    if metadata.get("session"):
        session = Path(metadata["session"])
    else:
        candidates = list(sessions.glob("*.jsonl"))
        if len(candidates) != 1:
            raise ValueError("Research has no unambiguous native session to resume")
        session = candidates[0]
    if session.parent != sessions or not session.is_file():
        raise ValueError("Research has no safe native session to resume")
    validate_native(session, metadata["sessionId"])
    validate_sessions(sessions)
    return session


def validate_native(session, session_id):
    with open_private(session) as stream:
        if os.fstat(stream.fileno()).st_size > SESSION_BYTES:
            raise ValueError("Research native session exceeds the 16 MiB budget")
        header = json.loads(stream.readline(64 * 1024))
    if header.get("type") != "session" or header.get("id") != session_id:
        raise ValueError("Research native session identity does not match its owner")


def run_turn(
    config_path, state, parent, name, task, *, cwd=None, resume=False, timeout=None, env=None
):
    env = dict(os.environ if env is None else env)
    agent, expected_state = caller_paths(env)
    if (
        state != expected_state
        or env.get("PI_CODING_AGENT_DIR") != str(agent)
        or env.get("PI_RE_CHILD") == "1"
        or env.get("PI_RE_RESEARCH") == "1"
        or env.get("PI_RE_CONFIG") != str(config_path)
    ):
        raise ValueError("Research delegation requires the root independent RE profile")
    if not NAME.fullmatch(name):
        raise ValueError("Use a lowercase research name of at most 48 letters, digits, _ or -")
    if not task.strip() or "\0" in task or len(task.encode()) > PROMPT_BYTES:
        raise ValueError("Research input must be nonempty UTF-8 text of at most 64 KiB")
    if not config_path.is_absolute() or config_path.stat().st_size > 1024 * 1024:
        raise ValueError("Invalid public research configuration")
    raw = config_path.read_bytes()
    config = json.loads(raw)
    budgets = policy(config)
    deadline = budgets["defaultTimeoutSeconds"] if timeout is None else timeout
    if type(deadline) is not int or not 1 <= deadline <= budgets["maxTimeoutSeconds"]:
        raise ValueError("Research timeout exceeds the configured finite budget")
    resources = Path(config["resources"])
    for path in (Path(config["pi"]), resources / "research-tools.ts", resources / "research.md"):
        if not path.is_absolute() or not path.is_file():
            raise ValueError("Pinned research runtime resource is missing")
    private_directory(state)
    key = parent_key(state, parent)
    root = state / "research"
    owner = root / key
    worker = owner / name
    for directory in (root, owner):
        private_directory(directory)
    with exclusive(
        owner / f"{name}.lock", "This named research worker is already running"
    ) as writer_lock:
        if resume:
            if not worker.is_dir():
                raise ValueError("Unknown research worker name for this parent")
        elif worker.exists():
            raise ValueError("Research name already exists; use research_subagent_message")
        sessions = worker / "sessions"
        metadata_path = worker / "metadata.json"
        fingerprint = hashlib.sha256(raw).hexdigest()
        if resume:
            metadata = read_metadata(metadata_path)
            cwd = Path(metadata["cwd"])
            session = validate_resume(metadata, fingerprint, cwd, sessions)
            metadata["session"] = str(session)
        else:
            if cwd is None or not cwd.is_absolute() or not cwd.is_dir():
                raise ValueError("Research source root must be an existing absolute directory")
            no_symlinks(cwd)
            # Whole-home/root review would include credentials and unrelated private state.
            if cwd == Path("/") or cwd == Path(env["HOME"]) or agent.is_relative_to(cwd):
                raise ValueError("Select a specific source directory, not the host or agent home")
            metadata = {
                "version": 1,
                "config": fingerprint,
                "cwd": str(cwd),
                "sessionId": str(uuid.uuid4()),
                "phase": "new",
                "turn": 0,
            }
            session = None
        if not cwd.is_dir():
            raise ValueError("The pinned research source root no longer exists")
        no_symlinks(cwd)
        with slot(root, budgets["maxConcurrent"]) as capacity_lock:
            private_directory(worker)
            private_directory(sessions)
            turn = worker / ("turn-" + uuid.uuid4().hex)
            private_directory(turn)
            with contextlib.ExitStack() as stack:
                files = {
                    label: stack.enter_context(open_private(turn / filename, exclusive=True))
                    for label, filename in (
                        ("prompt", "prompt.txt"),
                        ("events", "events.jsonl"),
                        ("stderr", "stderr.txt"),
                        ("tools", "tool-text.txt"),
                    )
                }
                files["prompt"].write(task.encode())
                files["prompt"].flush()
                metadata.update(phase="starting", writer=None)
                write_private(metadata_path, metadata)
                child_env = child_environment(config_path, sessions, env)
                child_env.update(
                    PI_CODING_AGENT_DIR=str(agent),
                    PI_RE_RESEARCH="1",
                    PI_RE_RESEARCH_ROOT=str(cwd),
                )
                command = [
                    config["pi"],
                    "--no-approve",
                    "--no-context-files",
                    "--no-skills",
                    "--no-extensions",
                    "--no-prompt-templates",
                    "--no-themes",
                    "--offline",
                    "--no-builtin-tools",
                    "--no-mcp",
                    "--tools",
                    "research_read,research_list,web_search,web_fetch",
                    "--session-dir",
                    str(sessions),
                    "--append-system-prompt",
                    str(resources / "research.md"),
                    "--extension",
                    str(resources / "research-tools.ts"),
                    "--extension",
                    config["webSearchExtension"],
                    "--extension",
                    config["webFetchExtension"],
                    "--provider",
                    PROVIDER,
                    "--model",
                    MODEL,
                    "--thinking",
                    "high",
                    "--print",
                    "--mode",
                    "json",
                ]
                command.extend(
                    ["--session", str(session)]
                    if resume
                    else ["--session-id", metadata["sessionId"]]
                )
                command.extend(["--", "Read-only documentation/source-review task:\n\n" + task])
                started = time.monotonic()
                events = Events(files["tools"])
                cancelled = False

                def cancel(_signum, _frame):
                    nonlocal cancelled
                    cancelled = True

                old = {sig: signal.signal(sig, cancel) for sig in (signal.SIGTERM, signal.SIGINT)}
                proc = None
                parent_pid = os.getppid()
                status = "ok"
                error = ""
                counts = {"events": 0, "stderr": 0}
                truncated = {"events": False, "stderr": False}
                next_storage_check = started
                try:
                    helper_pid = os.getpid()
                    proc = subprocess.Popen(
                        command,
                        cwd=cwd,
                        env=child_env,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True,
                        pass_fds=(writer_lock.fileno(), capacity_lock.fileno()),
                        preexec_fn=lambda: die_with_helper(helper_pid),
                    )
                    metadata.update(phase="running", writer=process_identity(proc.pid))
                    write_private(metadata_path, metadata)
                    with selectors.DefaultSelector() as selector:
                        for stream, label in ((proc.stdout, "events"), (proc.stderr, "stderr")):
                            os.set_blocking(stream.fileno(), False)
                            selector.register(stream, selectors.EVENT_READ, label)
                        while selector.get_map() or child_running(proc):
                            if cancelled or os.getppid() != parent_pid:
                                status = "cancelled"
                                break
                            if time.monotonic() - started >= deadline:
                                status = "timeout"
                                break
                            if time.monotonic() >= next_storage_check:
                                if (
                                    sum(path.stat().st_size for path in sessions.glob("*.jsonl"))
                                    > SESSION_BYTES
                                ):
                                    status, error = (
                                        "error",
                                        "Research session exceeded its storage budget",
                                    )
                                    break
                                next_storage_check = time.monotonic() + 1
                            for selected, _ in selector.select(timeout=0.05):
                                chunk = os.read(selected.fd, 65536)
                                if not chunk:
                                    selector.unregister(selected.fileobj)
                                    continue
                                label = selected.data
                                cap = LOG_BYTES if label == "events" else STDERR_BYTES
                                remaining = cap - counts[label]
                                files[label].write(chunk[:remaining])
                                counts[label] += min(remaining, len(chunk))
                                truncated[label] |= len(chunk) > remaining
                                if label == "events":
                                    events.feed(chunk)
                except (OSError, subprocess.SubprocessError):
                    status, error = "error", "Unable to launch/read the pinned research worker"
                finally:
                    if proc is not None:
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(proc.pid, signal.SIGTERM)
                        grace = time.monotonic() + 0.75
                        while child_running(proc) and time.monotonic() < grace:
                            time.sleep(0.025)
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
                        proc.stdout.close()
                        proc.stderr.close()
                    for sig, handler in old.items():
                        signal.signal(sig, handler)
                events.finish()
                validate_sessions(sessions)
                native = list(sessions.glob("*.jsonl"))
                if len(native) == 1:
                    validate_native(native[0], metadata["sessionId"])
                    metadata["session"] = str(native[0])
                elif native:
                    raise ValueError("Unexpected research native-session inventory")
                metadata.update(phase="finished", writer=None, turn=metadata["turn"] + 1)
                write_private(metadata_path, metadata)
                if status == "ok":
                    if (
                        events.model_mismatch
                        or proc.returncode != 0
                        or not events.assistants
                        or events.stop_reason in ("error", "aborted", "pending", "deferred")
                    ):
                        status = "error"
                    elif (
                        events.partial
                        or any(truncated.values())
                        or events.stop_reason in ("length", "toolUse")
                    ):
                        status = "partial"
                summary = bounded_summary(
                    {
                        "name": name,
                        "status": status,
                        "provider": PROVIDER,
                        "model": MODEL,
                        "turn": metadata["turn"],
                        "resumable": bool(metadata.get("session")),
                        "executionMode": "read-only-tools-not-host-sandbox",
                        "durationSeconds": round(time.monotonic() - started, 3),
                        "timeoutSeconds": deadline,
                        "result": events.final or events.preview,
                        "error": error
                        or (
                            "Unexpected research model/provider"
                            if events.model_mismatch
                            else events.error
                        ),
                        "usage": events.usage,
                        "artifacts": {"turn": str(turn)},
                    }
                )
                write_private(turn / "summary.json", summary)
                return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--timeout", type=int)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(PROMPT_BYTES + 1)
        if len(raw) > PROMPT_BYTES:
            raise ValueError("Research input exceeds 64 KiB")
        summary = run_turn(
            args.config,
            args.state_dir,
            args.parent,
            args.name,
            raw.decode(),
            cwd=args.cwd,
            resume=args.resume,
            timeout=args.timeout,
        )
        print(json.dumps(summary, ensure_ascii=False))
        return 0 if summary["status"] in ("ok", "partial") else 1
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"name": args.name, "status": "blocked", "error": str(error)[:2048]}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
