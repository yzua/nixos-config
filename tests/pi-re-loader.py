#!/usr/bin/env python3
"""Installed Pi loader isolation with a loopback mock provider, no real login/model."""

import argparse
import http.server
import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    launch = parser.add_mutually_exclusive_group(required=True)
    launch.add_argument("--pi", type=Path, help="Test checkout resources with this Pi executable")
    launch.add_argument("--pi-re", type=Path, help="Test this installed global pi-re launcher")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    code = root / "home-manager/modules/ai/pi-re"
    observed = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers["Content-Length"])
            assert length < 1024 * 1024
            observed.append(json.loads(self.rfile.read(length)))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for delta, finish in (
                ({"role": "assistant", "content": "LOADER_FIXTURE_OK"}, None),
                ({}, "stop"),
            ):
                chunk = {
                    "id": "fixture",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": "fixture",
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
                }
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

    with tempfile.TemporaryDirectory(prefix="pi-re-loader-") as temporary:
        home = Path(temporary)
        project = home / "hostile-project"
        project.mkdir()
        (project / "AGENTS.md").write_text("UNTRUSTED_CONTEXT_CANARY_DO_NOT_LOAD")
        extension = project / ".pi/extensions"
        extension.mkdir(parents=True)
        marker = home / "extension-ran"
        (extension / "unsafe.ts").write_text(
            f'import fs from "node:fs"; export default function() {{ fs.writeFileSync({json.dumps(str(marker))}, "unsafe"); }}'
        )
        skill = project / ".pi/skills/unreviewed"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: UNREVIEWED_SKILL_CANARY\ndescription: Never load this.\n---\nUnsafe fixture"
        )
        source = home / "coding-fixture"
        source.mkdir()
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            model = {
                "id": "fixture",
                "name": "fixture",
                "reasoning": False,
                "input": ["text"],
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                "contextWindow": 128000,
                "maxTokens": 1024,
            }
            models = {
                "providers": {
                    "fixture": {
                        "baseUrl": f"http://127.0.0.1:{server.server_port}/v1",
                        "api": "openai-completions",
                        "apiKey": "FIXTURE_PRIVATE_KEY_CANARY",
                        "models": [model],
                    }
                }
            }
            data = home / "isolated-data"
            state = home / "isolated-state"
            agent = data / "pi-re/agent"
            re_state = state / "pi-re"
            destination = agent if args.pi_re else source
            for directory in (agent, re_state):
                directory.mkdir(parents=True, mode=0o700)
            for name, value in {
                "settings.json": {
                    "defaultProvider": "fixture",
                    "defaultModel": "fixture",
                    "defaultProjectTrust": "never",
                    "extensions": ["-builtin:mcp"],
                    "enableInstallTelemetry": False,
                    "enableAnalytics": False,
                },
                "models.json": models,
                "auth.json": {},
            }.items():
                path = destination / name
                path.write_text(json.dumps(value))
                path.chmod(0o600)
            env = os.environ.copy()
            for key in list(env):
                if (
                    key.startswith(("PI_", "XDG_"))
                    or key.endswith(("_API_KEY", "_TOKEN"))
                    or key in ("IN_NIX_SHELL", "NIX_BUILD_TOP")
                ):
                    del env[key]
            env.update(HOME=str(home), XDG_DATA_HOME=str(data), XDG_STATE_HOME=str(state))
            if args.pi_re:
                # The marker short-circuits initialization before any real coding login is read.
                marker_path = re_state / "initialized-v1.json"
                marker_path.write_text(
                    json.dumps({"version": 1, "credentialMode": "independent-copy"})
                )
                marker_path.chmod(0o600)
                command = [str(args.pi_re.absolute())]
                doctor = subprocess.run(
                    [*command, "doctor", "--json"],
                    cwd=project,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                assert doctor.returncode == 0, doctor.stderr[-2000:]
                available = {
                    item["id"]
                    for item in json.loads(doctor.stdout)["capabilities"]
                    if item["enabled"]
                }
                assert {
                    "android-static",
                    "android-lab",
                    "agent-device",
                    "traffic",
                    "frida",
                } <= available
            else:
                runtime = home / "config.json"
                runtime.write_text(
                    json.dumps(
                        {
                            "pi": str(args.pi.resolve()),
                            "resources": str(code),
                            "sourceAgentDir": str(source),
                            "capabilities": [],
                        }
                    )
                )
                env["PI_RE_CONFIG"] = str(runtime)
                command = [os.sys.executable, "-B", str(code / "launcher.py")]
            result = subprocess.run(
                [
                    *command,
                    "--provider",
                    "fixture",
                    "--model",
                    "fixture",
                    "--thinking",
                    "off",
                    "--print",
                    "--mode",
                    "json",
                    "Check the loader fixture; don't call tools.",
                ],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            assert result.returncode == 0, result.stderr[-2000:]
            assert "LOADER_FIXTURE_OK" in result.stdout, result.stdout[-2000:]
            assert observed, "Mock provider was not contacted"
            body = json.dumps(observed)
            assert "UNTRUSTED_CONTEXT_CANARY" not in body
            assert "UNREVIEWED_SKILL_CANARY" not in body
            assert "FIXTURE_PRIVATE_KEY_CANARY" not in body + result.stdout + result.stderr
            assert "host" in body and "sandbox" in body
            for name in (
                "re-intake",
                "android-static",
                "android-runtime",
                "web-protocol",
                "native-analysis",
                "finding-validation",
                "adapter-build",
                "re-browser",
                "re-device",
            ):
                assert name in body, f"Reviewed skill missing: {name}"
            tool_names = {
                tool["function"]["name"]
                for request in observed
                for tool in request.get("tools", [])
            }
            assert {"read", "bash", "edit", "write", "re_subagent"} <= tool_names, tool_names
            assert not marker.exists(), "Hostile project extension was loaded"
            # Initialization diagnostics belong on stderr, preserving JSON mode stdout.
            for line in result.stdout.splitlines():
                json.loads(line)
            sessions = list((re_state / "sessions").glob("*.jsonl"))
            assert sessions, "No separate native session was written"
            print(
                f"{'Global pi-re' if args.pi_re else 'Installed Pi'} loader: all nine reviewed skills, "
                "contract/tools, hostile cwd excluded, isolated JSON/session state"
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    main()
