#!/usr/bin/env python3
"""Live offline pi-re question + Herdr cold restore, with private fixtures and no model calls."""

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CODE = REPO / "home-manager/modules/ai/pi-re"
PI_CODE = REPO / "home-manager/modules/ai/pi"


def main():
    name = "re-test-" + uuid.uuid4().hex[:10]
    # Supply the real package independently of a possible installed dispatcher.
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pi", type=Path, required=True, help="Pinned real Pi executable")
    args = parser.parse_args()
    pi = args.pi.resolve()
    integration = (
        Path(shutil.which("herdr")).resolve().parents[1]
        / "share/herdr/integrations/pi/herdr-agent-state.ts"
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("HERDR_", "PI_", "TMUX", "XDG_"))
    }
    with tempfile.TemporaryDirectory(prefix=name) as temporary:
        root = Path(temporary)
        (root / ".zshrc").write_text("# Private fixture, no setup wizard.\n")
        state = root / "state/pi-re"
        agent = root / "data/pi-re/agent"
        state.mkdir(parents=True, mode=0o700)
        agent.mkdir(parents=True, mode=0o700)

        def private_json(path, value):
            path.write_text(json.dumps(value))
            path.chmod(0o600)

        private_json(
            state / "initialized-v1.json", {"version": 1, "credentialMode": "independent-copy"}
        )
        private_json(
            agent / "settings.json",
            {
                "defaultProvider": "fixture",
                "defaultModel": "fixture",
                "defaultProjectTrust": "never",
                "extensions": ["-builtin:mcp"],
                "enableInstallTelemetry": False,
                "enableAnalytics": False,
            },
        )
        private_json(agent / "auth.json", {})
        private_json(
            agent / "models.json",
            {
                "providers": {
                    "fixture": {
                        "baseUrl": "http://127.0.0.1:9/v1",
                        "api": "openai-completions",
                        "apiKey": "unused-fixture",
                        "models": [
                            {
                                "id": "fixture",
                                "name": "Offline fixture",
                                "reasoning": False,
                                "input": ["text"],
                                "contextWindow": 100000,
                                "maxTokens": 1024,
                                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                            }
                        ],
                    }
                }
            },
        )
        log = root / "starts.jsonl"
        question = root / "question-fixture.ts"
        question.write_text(f"""import question from {json.dumps(str(PI_CODE / "extensions/ask-user-question.ts"))};
import {{appendFileSync}} from "node:fs";
export default function(pi) {{
 let tool;
 question({{...pi, registerTool: value => {{tool=value; pi.registerTool(value);}}}});
 pi.on("session_start", (_,ctx) => appendFileSync({json.dumps(str(log))}, JSON.stringify({{
  mode:ctx.mode, file:ctx.sessionManager.getSessionFile(),
  tools:pi.getAllTools().map(t=>t.name), agentDir:process.env.PI_CODING_AGENT_DIR
 }})+"\\n"));
 pi.registerCommand("fixture-question", {{description:"Offline fixture", handler: async (_,ctx) => {{
  await tool.execute("fixture", {{question:"Allow offline RE fixture?", options:[{{label:"Continue"}}]}},
                     undefined, undefined, ctx);
 }}}});
}}""")
        config = root / "runtime.json"
        private_json(
            config,
            {
                "pi": str(pi),
                "resources": str(CODE),
                "python": os.sys.executable,
                "sourceAgentDir": str(root / "unused-coding-source"),
                "herdrIntegration": str(integration),
                "questionExtension": str(question),
                "capabilities": [],
            },
        )
        bindir = root / "bin"
        bindir.mkdir()
        for executable, command in {
            "pi": [os.sys.executable, str(PI_CODE / "resume-dispatch.py"), str(pi), "--"],
            "pi-re": [os.sys.executable, str(CODE / "launcher.py")],
        }.items():
            path = bindir / executable
            path.write_text(
                f'#!{shutil.which("bash")}\nexport PI_RE_CONFIG={shlex.quote(str(config))}\nexec {shlex.join(command)} "$@"\n'
            )
            path.chmod(0o755)
        hostile = root / ".pi/agent/extensions"
        hostile.mkdir(parents=True)
        marker = root / "coding-extension-ran"
        (hostile / "unsafe.ts").write_text(
            f'import fs from "node:fs"; export default function(){{fs.writeFileSync({json.dumps(str(marker))},"unsafe");}}'
        )
        env.update(
            HOME=str(root),
            PATH=f"{bindir}:{env['PATH']}",
            XDG_CONFIG_HOME=str(root / "config"),
            XDG_STATE_HOME=str(root / "state"),
            XDG_DATA_HOME=str(root / "data"),
            HERDR_CONFIG_PATH=str(root / "herdr.toml"),
        )
        (root / "herdr.toml").write_text(
            'onboarding = false\n[ui.toast]\ndelivery = "system"\ndelay_seconds = 1\n'
        )
        tmux = ["tmux", "-L", name, "-f", "/dev/null"]
        herdr = ["herdr", "--session", name]
        started = False

        def call(command, check=True):
            return subprocess.run(
                command, env=env, cwd=root, capture_output=True, text=True, timeout=15, check=check
            )

        def api(*arguments):
            output = call([*herdr, *arguments]).stdout
            return json.loads(output)["result"] if output.strip() else {}

        def wait(condition, message, timeout=15):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                value = condition()
                if value:
                    return value
                time.sleep(0.05)
            raise RuntimeError(message)

        def starts():
            return (
                [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            )

        def pane_status():
            return api("pane", "get", parent)["pane"]["agent_status"]

        def launch_herdr(new=False):
            # The holder keeps our private tmux session alive after Herdr stops.
            command = shlex.join(herdr) + "; sleep 120"
            call(
                [
                    *tmux,
                    "new-window" if new else "new-session",
                    "-d",
                    "-s" if not new else "-t",
                    name,
                    *([] if new else ["-x", "180", "-y", "55"]),
                    command,
                ]
            )

        try:
            launch_herdr()
            started = True

            def initial_pane():
                response = call([*herdr, "pane", "list"], check=False)
                if response.returncode:
                    return None
                panes = json.loads(response.stdout)["result"]["panes"]
                return panes[0]["pane_id"] if panes else None

            parent = wait(initial_pane, "Private Herdr did not start")
            time.sleep(0.5)
            api("pane", "run", parent, "pi-re --provider fixture --model fixture --thinking off")
            wait(lambda: len(starts()) == 1, "RE root did not initialize")
            api("pane", "run", parent, "/fixture-question")
            wait(lambda: pane_status() == "blocked", "Actual RE question did not report blocked")
            # Cancel only our synthetic question; no engagement or approval is involved.
            call([*herdr, "pane", "send-keys", parent, "esc"])
            wait(
                lambda: pane_status() in ("idle", "done"),
                "Cancelled RE question did not clear blocked",
            )
            first = starts()[0]
            # Pi lazily persists a new chat only after its first assistant turn.
            # Seed a native offline conversation so cold restore has real history,
            # without requesting any model or reading the user's login.
            session = Path(first["file"])
            assert session.is_relative_to(state / "sessions"), session
            if not session.exists():
                session.write_text(
                    json.dumps(
                        {
                            "type": "session",
                            "version": 3,
                            "id": session.stem.split("_")[-1],
                            "timestamp": "2026-01-01T00:00:00.000Z",
                            "cwd": str(root),
                        }
                    )
                    + "\n"
                    + json.dumps(
                        {
                            "type": "message",
                            "id": "fixture-message",
                            "parentId": None,
                            "timestamp": "2026-01-01T00:00:00.000Z",
                            "message": {
                                "role": "assistant",
                                "content": [
                                    {"type": "text", "text": "Persisted offline RE fixture"}
                                ],
                                "api": "openai-completions",
                                "provider": "fixture",
                                "model": "fixture",
                                "stopReason": "stop",
                                "timestamp": 0,
                                "usage": {
                                    "input": 0,
                                    "output": 0,
                                    "cacheRead": 0,
                                    "cacheWrite": 0,
                                    "totalTokens": 0,
                                    "cost": {
                                        "input": 0,
                                        "output": 0,
                                        "cacheRead": 0,
                                        "cacheWrite": 0,
                                        "total": 0,
                                    },
                                },
                            },
                        }
                    )
                    + "\n"
                )
                session.chmod(0o600)
            assert first["mode"] == "tui" and first["agentDir"] == str(agent), first
            assert {"ask_user_question", "re_subagent"} <= set(first["tools"]), first
            assert not {"subagent", "subagent_message", "ask_question"} & set(first["tools"]), first
            assert not marker.exists(), "Coding-profile extension leaked into RE"
            call([*herdr, "session", "stop", name])
            launch_herdr(new=True)
            try:
                wait(
                    lambda: len(starts()) == 2,
                    "Herdr cold restore did not reopen RE root",
                    timeout=15,
                )
            except RuntimeError as error:
                snapshot = call(
                    [*herdr, "pane", "read", parent, "--format", "text"], check=False
                ).stdout
                raise RuntimeError(str(error) + "\n" + snapshot) from error
            second = starts()[1]
            assert second == first, (first, second)
            assert not marker.exists(), "Cold restore loaded coding-profile extension"
            call([*herdr, "session", "stop", name])
            # Fresh direct tmux shell, equivalent to `p --session PATH`.
            call(
                [
                    *tmux,
                    "new-window",
                    "-d",
                    "-t",
                    name,
                    shlex.join(["pi", "--approve", "--session", str(session)]) + "; sleep 120",
                ]
            )
            wait(lambda: len(starts()) == 3, "Direct tmux resume did not preserve RE profile")
            assert starts()[2] == first, (first, starts()[2])
            assert not marker.exists(), "Tmux resume loaded coding-profile extension"
            print(
                "Live RE: actual question blocked/cancelled; Herdr cold restore and direct tmux resume preserve session, RE profile and tools"
            )
        finally:
            if started:
                call([*herdr, "session", "stop", name], check=False)
                call([*herdr, "session", "delete", name], check=False)
                call([*tmux, "kill-server"], check=False)


if __name__ == "__main__":
    main()
