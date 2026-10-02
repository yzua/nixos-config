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
    parser.add_argument("--pi", type=Path, required=True)
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
            for name, value in {
                "settings.json": {"defaultProvider": "fixture", "defaultModel": "fixture"},
                "models.json": models,
                "auth.json": {},
            }.items():
                (source / name).write_text(json.dumps(value))
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
            env = os.environ.copy()
            for key in list(env):
                if key.startswith("PI_") or key.startswith("XDG_"):
                    del env[key]
            env.update(HOME=str(home), PI_RE_CONFIG=str(runtime))
            result = subprocess.run(
                [
                    os.sys.executable,
                    "-B",
                    str(code / "launcher.py"),
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
            assert "FIXTURE_PRIVATE_KEY_CANARY" not in body
            assert "host" in body and "sandbox" in body
            for name in ("re-intake", "android-static", "android-runtime", "re-device"):
                assert name in body, f"Reviewed skill missing: {name}"
            assert not marker.exists(), "Hostile project extension was loaded"
            # Initialization diagnostics belong on stderr, preserving JSON mode stdout.
            for line in result.stdout.splitlines():
                json.loads(line)
            sessions = list((home / ".local/state/pi-re/sessions").glob("*.jsonl"))
            assert sessions, "No separate native session was written"
            print(
                "Installed Pi loader: explicit RE skills/contract, hostile context excluded, isolated JSON/session state"
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    main()
