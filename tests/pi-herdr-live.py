#!/usr/bin/env python3
"""Isolated live Herdr tab topology/cleanup test. No models, credentials or user sessions."""

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUX = (
    ROOT
    / "home-manager/modules/ai/pi/extensions/interactive-subagents/pi-extension/subagents/tmux.ts"
)


def main():
    for tool in ("herdr", "tmux", "bun"):
        if not shutil.which(tool):
            raise RuntimeError(f"Missing {tool}")
    name = "pi-tabs-test-" + uuid.uuid4().hex[:10]
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("HERDR_", "PI_", "TMUX", "XDG_"))
    }
    with tempfile.TemporaryDirectory(prefix=name) as temporary:
        root = Path(temporary)
        (root / ".zshrc").write_text("# Isolated fixture: suppress first-run setup.\n")
        env.update(
            HOME=str(root),
            XDG_CONFIG_HOME=str(root / "config"),
            XDG_STATE_HOME=str(root / "state"),
            XDG_DATA_HOME=str(root / "data"),
            HERDR_CONFIG_PATH=str(root / "herdr.toml"),
        )
        (root / "herdr.toml").write_text("onboarding = false\n")
        tmux = ["tmux", "-L", name, "-f", "/dev/null"]
        herdr = ["herdr", "--session", name]

        def call(command, check=True):
            return subprocess.run(
                command, env=env, cwd=root, capture_output=True, text=True, timeout=10, check=check
            )

        def api(*args):
            output = call([*herdr, *args]).stdout
            return json.loads(output)["result"] if output.strip() else {}

        started = False
        try:
            call(
                [*tmux, "new-session", "-d", "-s", name, "-x", "180", "-y", "55", shlex.join(herdr)]
            )
            started = True
            deadline = time.monotonic() + 10
            while True:
                response = call([*herdr, "pane", "list"], check=False)
                if response.returncode == 0:
                    parent = json.loads(response.stdout)["result"]["panes"][0]["pane_id"]
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("Isolated Herdr did not start")
                time.sleep(0.05)
            caller = api("pane", "get", parent)["pane"]
            workspace = caller["workspace_id"]
            socket_file = root / "socket-path"
            api(
                "pane",
                "run",
                parent,
                f'printf "%s" "$HERDR_SOCKET_PATH" > {shlex.quote(str(socket_file))}',
            )
            deadline = time.monotonic() + 5
            while not socket_file.exists() or socket_file.stat().st_size == 0:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "Owned shell did not record its socket: "
                        + call([*herdr, "pane", "read", parent, "--format", "text"]).stdout
                    )
                time.sleep(0.025)
            # The first UI attach can resize the headless server's initial grid.
            time.sleep(0.5)
            before = api("pane", "layout", "--pane", parent)
            tabs_before = api("tab", "list", "--workspace", workspace)
            probe = root / "probe.ts"
            probe.write_text(
                f"import * as mux from {json.dumps(str(MUX))};\n"
                'const panes = ["scout", "reviewer", "worker"].map(mux.createSurface);\n'
                "console.log(JSON.stringify(panes));\n"
            )
            child_env = dict(
                env,
                HERDR_ENV="1",
                HERDR_PANE_ID=parent,
                HERDR_SOCKET_PATH=socket_file.read_text(),
                TMUX="wrong-outer,1,0",
                TMUX_PANE="%999",
            )
            result = subprocess.run(
                [shutil.which("bun"), str(probe)],
                env=child_env,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert result.returncode == 0, result.stderr
            panes = json.loads(result.stdout)
            assert len(set(panes)) == 3, panes
            after = api("pane", "layout", "--pane", parent)
            assert before == after, (before, after)
            tabs = api("tab", "list", "--workspace", workspace)
            assert len(tabs["tabs"]) == len(tabs_before["tabs"]) + 3, tabs
            old_ids = {tab["tab_id"] for tab in tabs_before["tabs"]}
            new_tabs = [tab for tab in tabs["tabs"] if tab["tab_id"] not in old_ids]
            assert {tab["label"] for tab in new_tabs} == {"scout", "reviewer", "worker"}, new_tabs
            assert all(not tab["focused"] for tab in new_tabs), new_tabs
            for pane in panes:
                api("pane", "close", pane)
            remaining = api("tab", "list", "--workspace", workspace)
            assert remaining == tabs_before, (tabs_before, remaining)
            print(
                "Live Herdr: three separate named tabs; parent geometry/focus preserved; owned cleanup removes tabs"
            )
        finally:
            if started:
                call([*herdr, "session", "stop", name], check=False)
                call([*herdr, "session", "delete", name], check=False)
                call([*tmux, "kill-server"], check=False)


if __name__ == "__main__":
    main()
