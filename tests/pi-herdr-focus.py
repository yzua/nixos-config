#!/usr/bin/env python3
"""Live, offline regression for tmux FocusOut -> Herdr desktop attention alerts.

Requires installed Herdr/tmux/strace, a graphical session, and activated tmux
configuration. Uses only its own named Herdr session and separate tmux server.
Sends generic test desktop notifications; no model calls or credentials.
"""

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path


def main():
    for tool in ["herdr", "tmux", "strace"]:
        if not shutil.which(tool):
            raise RuntimeError(f"Missing required tool: {tool}")
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise RuntimeError("A graphical session is required for system notification delivery")
    name = f"pi-focus-test-{uuid.uuid4().hex[:10]}"
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"TMUX", "TMUX_PANE"} and not key.startswith("HERDR_")
    }
    with tempfile.TemporaryDirectory(prefix="pi-herdr-focus-") as temporary:
        root = Path(temporary)
        config = root / "config.toml"
        config.write_text(
            'onboarding = false\n[ui.toast]\ndelivery = "system"\ndelay_seconds = 1\n'
        )
        env["HERDR_CONFIG_PATH"] = str(config)
        mux = ["tmux", "-L", name]
        herdr = ["herdr", "--session", name]
        trace = root / "exec.trace"
        client = None
        started = False

        def call(args, check=True):
            return subprocess.run(
                args, env=env, capture_output=True, text=True, timeout=10, check=check
            )

        def count_notifications():
            return trace.read_text().count("/bin/notify-send") if trace.exists() else 0

        try:
            launch = shlex.join(["strace", "-f", "-e", "trace=execve", "-o", str(trace), *herdr])
            call([*mux, "new-session", "-d", "-s", name, "-x", "180", "-y", "55", launch])
            started = True
            configured_focus = call([*mux, "show-options", "-g", "focus-events"]).stdout.strip()
            assert configured_focus == "focus-events on", configured_focus
            deadline = time.monotonic() + 10
            while True:
                response = call([*herdr, "pane", "list"], check=False)
                if response.returncode == 0:
                    pane = json.loads(response.stdout)["result"]["panes"][0]["pane_id"]
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("Test Herdr server did not start")
                time.sleep(0.05)
            call([*mux, "new-window", "-d", "-t", name, "-n", "other"])
            windows = call(
                [*mux, "list-windows", "-t", name, "-F", "#{window_id}"]
            ).stdout.splitlines()
            with (root / "control.log").open("w") as control_log:
                client = subprocess.Popen(
                    [*mux, "-C", "attach-session", "-t", name],
                    env=env,
                    stdin=subprocess.PIPE,
                    stdout=control_log,
                    stderr=control_log,
                    text=True,
                )
                results = {}
                seq = 0
                for setting in ["off", "on"]:
                    call([*mux, "set-option", "-g", "focus-events", setting])
                    call([*mux, "select-window", "-t", windows[0]])
                    time.sleep(0.1)
                    call([*mux, "select-window", "-t", windows[1]])
                    time.sleep(0.1)
                    before = count_notifications()
                    for state in ["working", "blocked"]:
                        seq += 1
                        call(
                            [
                                *herdr,
                                "pane",
                                "report-agent",
                                pane,
                                "--source",
                                "test:focus",
                                "--agent",
                                "pi",
                                "--state",
                                state,
                                "--seq",
                                str(seq),
                            ]
                        )
                    status = json.loads(call([*herdr, "pane", "get", pane]).stdout)["result"][
                        "pane"
                    ]
                    assert status["agent_status"] == "blocked", status
                    deadline = time.monotonic() + 2.5
                    while time.monotonic() < deadline and count_notifications() == before:
                        time.sleep(0.025)
                    results[setting] = count_notifications() > before
                print(
                    json.dumps(
                        {"focus_off_notifies": results["off"], "focus_on_notifies": results["on"]},
                        indent=2,
                    )
                )
                assert not results["off"], "Disabled-focus baseline unexpectedly notified"
                assert results["on"], "FocusOut did not restore the Herdr system notification"
        finally:
            if client is not None:
                if client.poll() is None:
                    client.stdin.write("detach-client\n")
                    client.stdin.flush()
                try:
                    client.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    client.kill()
                    client.communicate()
            # Never stop any server/session that this test did not create.
            if started:
                call([*herdr, "session", "stop", name], check=False)
                call([*herdr, "session", "delete", name], check=False)
                call([*mux, "kill-server"], check=False)


if __name__ == "__main__":
    main()
