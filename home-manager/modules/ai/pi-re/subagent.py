#!/usr/bin/env python3
"""Owned, bounded Flash jobs for pi-re (host mode, NOT a sandbox).

CLI: --config generated.json --state-dir <caller RE state> --cwd <absolute>
Task arrives on stdin. Only a fresh native session is supported; no resume API.
The launcher must honor PI_RE_CHILD_SESSION_DIR and disable delegation for children.
No auth/settings files are inspected, copied or changed by this helper.
"""

import argparse
import contextlib
import ctypes
import fcntl
import json
import math
import os
import selectors
import signal
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

PROVIDER = "zai"
MODEL = "glm-5.3-flash"
DEADLINE_SECONDS = 180
RESULT_BYTES = 16 * 1024
PROMPT_BYTES = 64 * 1024
LINE_BYTES = 256 * 1024
LOG_BYTES = 2 * 1024 * 1024
STDERR_BYTES = 256 * 1024
TEXT_BYTES = 64 * 1024
SESSION_ENV = (
    "PI_SESSION_FILE",
    "PI_SESSION_ID",
    "PI_PROVIDER",
    "PI_MODEL",
    "PI_REASONING_LEVEL",
    "PI_CODING_AGENT_SESSION_DIR",
    "PI_RE_CHILD_SESSION_DIR",
)


def caller_paths(env):
    home = Path(env["HOME"])
    data = Path(env.get("XDG_DATA_HOME") or home / ".local/share")
    state = Path(env.get("XDG_STATE_HOME") or home / ".local/state")
    if not all(p.is_absolute() for p in (home, data, state)):
        raise ValueError("Caller RE paths must be absolute")
    return data / "pi-re/agent", state / "pi-re"


def no_symlinks(path):
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Artifact paths must be absolute without parent traversal")
    for component in (*reversed(path.parents), path):
        if component.is_symlink():
            raise ValueError("RE artifacts must not contain symlinks")


def private_directory(path):
    no_symlinks(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("RE artifact directories must be private and caller-owned")


def validate_file(fd, path):
    no_symlinks(path)
    info = os.fstat(fd)
    entry = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
        or info.st_mode & 0o077
        or (info.st_dev, info.st_ino) != (entry.st_dev, entry.st_ino)
    ):
        raise ValueError("Unsafe RE artifact: require a private caller-owned single-link file")


def open_private(path, exclusive=False):
    no_symlinks(path)
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
    if exclusive:
        flags |= os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        validate_file(fd, path)
        return os.fdopen(fd, "w+b" if exclusive else "r+b")
    except BaseException:
        os.close(fd)
        raise


@contextlib.contextmanager
def child_slot(directory):
    """Kernel-held leases, not PID files: crashes release them; never kill lease owners."""
    private_directory(directory)
    for number in range(2):
        lock = open_private(directory / f"slot-{number}.lock")
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            yield number
            return
        finally:
            lock.close()
    raise ValueError("At most two RE children may run concurrently")


def clip(text, limit):
    return text.encode("utf-8", errors="replace")[:limit].decode("utf-8", errors="ignore")


def text_content(content):
    if isinstance(content, str):
        return clip(content, TEXT_BYTES)
    parts = []
    remaining = TEXT_BYTES
    if isinstance(content, list):
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
            ):
                piece = clip(block["text"], remaining)
                parts.append(piece)
                remaining -= len(piece.encode("utf-8"))
                if remaining <= 0:
                    break
    return clip("\n".join(parts), TEXT_BYTES)


class Events:
    """Bounded LF-only JSONL parser. Completed messages replace delta previews."""

    def __init__(self, tools):
        self.buffer = bytearray()
        self.dropping = False
        self.partial = False
        self.final = ""
        self.preview = ""
        self.stop_reason = None
        self.error = ""
        self.assistants = 0
        self.run_messages = 0
        self.model_mismatch = False
        self.tools = tools
        self.tool_bytes = 0
        self.usage = {
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0,
            "totalTokens": 0,
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "total": 0},
        }

    def feed(self, chunk):
        # Oversized records are discarded through LF, never accumulated without bound.
        for part in chunk.split(b"\n")[:-1]:
            self.segment(part, True)
        self.segment(chunk.rsplit(b"\n", 1)[-1], False)

    def segment(self, part, complete):
        if not self.dropping:
            if len(self.buffer) + len(part) > LINE_BYTES:
                self.buffer.clear()
                self.dropping = True
                self.partial = True
            else:
                self.buffer.extend(part)
        if complete:
            if not self.dropping:
                self.line(bytes(self.buffer))
            self.buffer.clear()
            self.dropping = False

    def finish(self):
        if self.buffer and not self.dropping:
            self.line(bytes(self.buffer))
        self.buffer.clear()

    def message(self, message):
        if not isinstance(message, dict):
            self.partial = True
            return
        role = message.get("role")
        if role == "assistant":
            self.assistants += 1
            self.run_messages += 1
            self.final = text_content(message.get("content"))
            self.preview = ""
            self.stop_reason = message.get("stopReason")
            self.error = clip(str(message.get("errorMessage") or ""), 2048)
            if (
                message.get("model", MODEL) != MODEL
                or message.get("provider", PROVIDER) != PROVIDER
            ):
                self.model_mismatch = True
            usage = message.get("usage")
            if isinstance(usage, dict):
                for key in self.usage:
                    value = usage.get(key)
                    if key == "cost":
                        if isinstance(value, dict):
                            for cost_key in self.usage["cost"]:
                                amount = value.get(cost_key)
                                if (
                                    isinstance(amount, (int, float))
                                    and not isinstance(amount, bool)
                                    and math.isfinite(amount)
                                    and amount >= 0
                                ):
                                    self.usage["cost"][cost_key] = min(
                                        1e15, self.usage["cost"][cost_key] + amount
                                    )
                    elif (
                        isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and math.isfinite(value)
                        and value >= 0
                    ):
                        self.usage[key] = min(1e15, self.usage[key] + value)
        elif role == "toolResult":
            self.tool_text(message.get("content"))

    def tool_text(self, content):
        data = (text_content(content) + "\n").encode("utf-8")
        remaining = TEXT_BYTES - self.tool_bytes
        self.tools.write(data[:remaining])
        self.tool_bytes += min(len(data), remaining)
        if len(data) > remaining:
            self.partial = True

    def line(self, data):
        if not data.strip():
            return
        try:
            event = json.loads(data)
        except (ValueError, UnicodeError, RecursionError):
            self.partial = True
            return
        if not isinstance(event, dict):
            self.partial = True
            return
        kind = event.get("type")
        if kind == "agent_start":
            self.run_messages = 0
        elif kind in ("message_end", "tool_result_end"):
            self.message(event.get("message"))
        elif kind == "agent_end" and not self.run_messages:
            messages = event.get("messages")
            if isinstance(messages, list):
                for message in messages:
                    self.message(message)
        elif kind == "tool_execution_end":
            result = event.get("result")
            if isinstance(result, dict):
                self.tool_text(result.get("content"))
        elif kind == "message_update":
            delta = event.get("assistantMessageEvent")
            if isinstance(delta, dict):
                if delta.get("type") == "text_delta" and isinstance(delta.get("delta"), str):
                    self.preview = clip(self.preview + delta["delta"], TEXT_BYTES)
                elif delta.get("type") == "error":
                    self.stop_reason = delta.get("reason", "error")
                    error = delta.get("error")
                    self.error = clip(
                        str(error.get("errorMessage") or "Provider stream error")
                        if isinstance(error, dict)
                        else "Provider stream error",
                        2048,
                    )
        elif kind == "auto_retry_end" and event.get("success") is False:
            self.stop_reason = "error"
            self.error = clip(str(event.get("finalError") or "Retries exhausted"), 2048)


def bounded_summary(summary):
    """Cap the entire serialized result, including JSON escaping and metadata."""
    summary["resultTruncated"] = False
    while len(json.dumps(summary, ensure_ascii=False).encode("utf-8")) > RESULT_BYTES:
        summary["resultTruncated"] = True
        text = summary["result"]
        if not text:
            raise ValueError("RE artifact metadata exceeds result budget")
        summary["result"] = clip(text, max(0, len(text.encode("utf-8")) - 1024))
    return summary


def validate_sessions(directory):
    """Only publish a session artifact root with private, safe native files beneath it."""
    count = 0
    for root, directories, files in os.walk(directory, followlinks=False):
        private_directory(Path(root))
        for name in directories:
            private_directory(Path(root) / name)
        for name in files:
            path = Path(root) / name
            no_symlinks(path)
            info = path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_nlink != 1
                or info.st_mode & 0o077
            ):
                raise ValueError("Unsafe native RE session artifact")
        count += len(directories) + len(files)
        if count > 1024:
            raise ValueError("Native RE session artifact catalog exceeds 1024 entries")


def die_with_helper(parent_pid):
    os.umask(0o077)  # Pi's own native session writes must also be private.
    # Linux backstop if the helper itself is killed before it can relay cleanup.
    # This protects the direct launcher/Pi child, not arbitrary escaped descendants.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(), "Cannot establish child ownership")
    if os.getppid() != parent_pid:
        os.kill(os.getpid(), signal.SIGKILL)


def child_running(proc):
    # WNOWAIT retains the leader as a zombie until owned group cleanup is complete,
    # preventing PID/process-group reuse while cancellation escalates.
    return os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None


def child_environment(config_path, sessions, env):
    result = dict(env)
    for name in list(result):
        if name in SESSION_ENV or name.startswith(("HERDR_", "TMUX", "PI_SUBAGENT")):
            del result[name]
    result.update(
        PI_RE_CONFIG=str(config_path),
        PI_RE_CHILD="1",
        PI_RE_CHILD_SESSION_DIR=str(sessions),
        PI_CODING_AGENT_SESSION_DIR=str(sessions),
        PI_OFFLINE="1",
    )
    return result


def run_job(config_path, state_dir, cwd, task, *, deadline=DEADLINE_SECONDS, env=None):
    env = dict(os.environ if env is None else env)
    started = time.monotonic()
    if not 0 < deadline <= DEADLINE_SECONDS:
        raise ValueError("Deadline must be finite and no more than 180 seconds")
    if env.get("PI_RE_CHILD") == "1":
        raise ValueError("RE children cannot delegate")
    agent, expected_state = caller_paths(env)
    if state_dir != expected_state or env.get("PI_CODING_AGENT_DIR") != str(agent):
        raise ValueError("Helper requires the caller's RE profile and exact RE state directory")
    if not cwd.is_absolute() or not cwd.is_dir():
        raise ValueError("cwd must be an existing absolute directory")
    if not task.strip() or "\x00" in task or len(task.encode("utf-8")) > PROMPT_BYTES:
        raise ValueError("Task must be nonempty UTF-8 text of at most 64 KiB without NUL")
    # Only read the generated public runtime configuration, never profile/auth files.
    if env.get("PI_RE_CONFIG") and env["PI_RE_CONFIG"] != str(config_path):
        raise ValueError("Foreign runtime configuration overrides are not supported")
    if not config_path.is_absolute() or config_path.stat().st_size > 1024 * 1024:
        raise ValueError("Invalid generated RE configuration")
    config = json.loads(config_path.read_text())
    python = Path(config["python"])
    resources = Path(config["resources"])
    launcher = resources / "launcher.py"
    if not python.is_absolute() or not resources.is_absolute() or not launcher.is_file():
        raise ValueError("Require absolute configured Python and reviewed launcher resource")
    private_directory(state_dir)
    root = state_dir / "subagents"
    private_directory(root)
    with child_slot(root):
        jobs = root / "jobs"
        private_directory(jobs)
        jobid = str(uuid.uuid4())
        job = jobs / jobid
        job.mkdir(mode=0o700)
        sessions = job / "sessions"
        private_directory(sessions)
        artifacts = {
            "prompt": job / "prompt.txt",
            "events": job / "events.jsonl",
            "stderr": job / "stderr.txt",
            "tools": job / "tool-text.txt",
            "result": job / "result.txt",
            "summary": job / "summary.json",
            "sessions": sessions,
        }
        with contextlib.ExitStack() as stack:
            files = {
                name: stack.enter_context(open_private(path, exclusive=True))
                for name, path in artifacts.items()
                if name != "sessions"
            }
            files["prompt"].write(task.encode("utf-8"))
            files["prompt"].flush()
            events = Events(files["tools"])
            cancelled = False

            def cancel(_signum, _frame):
                nonlocal cancelled
                cancelled = True

            old_signals = {
                sig: signal.signal(sig, cancel) for sig in (signal.SIGTERM, signal.SIGINT)
            }
            parent_pid = os.getppid()
            proc = None
            startup_error = ""
            status = "error"
            truncated = {"events": False, "stderr": False}
            counts = {"events": 0, "stderr": 0}
            try:
                # No shell, ambient agents, session controls or user-selectable model/resources.
                # Prefix prevents Pi's @file or /template prompt syntax from interpreting
                # caller text as a foreign file/resource selector, even after `--`.
                prompt = (
                    "Delegated RE task (use only the stated authorization and owned resources):\n\n"
                    + task
                )
                command = [
                    str(python),
                    str(launcher),
                    "--provider",
                    PROVIDER,
                    "--model",
                    MODEL,
                    "--thinking",
                    "high",
                    "--print",
                    "--mode",
                    "json",
                    "--",
                    prompt,
                ]
                helper_pid = os.getpid()
                proc = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=child_environment(config_path, sessions, env),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                    preexec_fn=lambda: die_with_helper(helper_pid),
                )
                status = "ok"
                with selectors.DefaultSelector() as selector:
                    for stream, name in ((proc.stdout, "events"), (proc.stderr, "stderr")):
                        os.set_blocking(stream.fileno(), False)
                        selector.register(stream, selectors.EVENT_READ, name)
                    while selector.get_map() or child_running(proc):
                        if cancelled or os.getppid() != parent_pid:
                            status = "cancelled"
                            break
                        if time.monotonic() - started >= deadline:
                            status = "timeout"
                            break
                        for key, _ in selector.select(timeout=0.05):
                            data = os.read(key.fd, 65536)
                            if not data:
                                selector.unregister(key.fileobj)
                                continue
                            name = key.data
                            cap = LOG_BYTES if name == "events" else STDERR_BYTES
                            remaining = cap - counts[name]
                            files[name].write(data[:remaining])
                            counts[name] += min(remaining, len(data))
                            truncated[name] |= len(data) > remaining
                            if name == "events":
                                events.feed(data)
            except (OSError, subprocess.SubprocessError):
                startup_error = "Unable to launch or read the configured RE child"
                status = "error"
            finally:
                if proc is not None:
                    # The fresh process group belongs to this Popen only. Never find/kill by name or stale PID.
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(proc.pid, signal.SIGTERM)
                    grace = time.monotonic() + 0.75
                    while child_running(proc) and time.monotonic() < grace:
                        time.sleep(0.025)
                    # Leader has not been reaped: this group cannot have been reused.
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                    proc.stdout.close()
                    proc.stderr.close()
                for sig, handler in old_signals.items():
                    signal.signal(sig, handler)
            events.finish()
            if status == "ok":
                if (
                    events.model_mismatch
                    or proc.returncode != 0
                    or events.stop_reason in ("error", "aborted", "pending", "deferred")
                    or not events.assistants
                ):
                    status = "error"
                elif (
                    events.partial
                    or any(truncated.values())
                    or events.stop_reason in ("length", "toolUse")
                ):
                    status = "partial"
            validate_sessions(sessions)
            result = events.final or events.preview
            files["result"].write(result.encode("utf-8"))
            summary = bounded_summary(
                {
                    "jobid": jobid,
                    "status": status,
                    "provider": PROVIDER,
                    "model": MODEL,
                    "thinking": "high",
                    "executionMode": "host-not-sandbox",
                    "exitCode": proc.returncode if proc else None,
                    "durationSeconds": round(time.monotonic() - started, 3),
                    "stopReason": clip(events.stop_reason, 64)
                    if isinstance(events.stop_reason, str)
                    else None,
                    "error": "Unexpected child model/provider"
                    if events.model_mismatch
                    else startup_error or events.error,
                    "result": result,
                    "logTruncated": truncated,
                    "parsePartial": events.partial,
                    "usage": events.usage,
                    "artifacts": {name: str(path) for name, path in artifacts.items()},
                }
            )
            files["summary"].write(json.dumps(summary, ensure_ascii=False).encode("utf-8"))
            for name, stream in files.items():
                stream.flush()
                validate_file(stream.fileno(), artifacts[name])
            private_directory(sessions)
            return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(PROMPT_BYTES + 1)
        if len(raw) > PROMPT_BYTES:
            raise ValueError("Task exceeds 64 KiB")
        summary = run_job(args.config, args.state_dir, args.cwd, raw.decode("utf-8"))
        print(json.dumps(summary, ensure_ascii=False))
        return 0 if summary["status"] in ("ok", "partial") else 1
    except (ValueError, OSError, KeyError, TypeError) as error:
        # No raw provider logs, task or configuration contents in blocked diagnostics.
        print(
            json.dumps(
                {
                    "jobid": None,
                    "status": "blocked",
                    "provider": PROVIDER,
                    "model": MODEL,
                    "executionMode": "host-not-sandbox",
                    "error": clip(str(error), 2048),
                    "artifacts": {},
                }
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
