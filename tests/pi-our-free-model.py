#!/usr/bin/env python3
"""Load both local proxy providers through native Pi without external requests."""

import http.server
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_test_support import isolated_environment, require_pi

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "home-manager/modules/ai/pi-base/extensions/our-free-model.ts"


class ChatFixture(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append((self.path, dict(self.headers), body))
        chunk = {"id": "fixture", "object": "chat.completion.chunk", "model": body["model"]}
        events = [
            {
                **chunk,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": "FREE_CHILD_OK"},
                        "finish_reason": None,
                    }
                ],
            },
            {**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ]
        raw = (
            "".join("data: " + json.dumps(event) + "\n\n" for event in events) + "data: [DONE]\n\n"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class LocalProxyTests(unittest.TestCase):
    def test_restricted_free_children_load_the_provider_on_launch_and_resume(self):
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ChatFixture)
        server.requests = []
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory(prefix="pi-free-child-") as temporary:
            root = Path(temporary)
            agent = root / "agent"
            agent.mkdir()
            (agent / "settings.json").write_text(
                json.dumps(
                    {
                        "defaultProvider": "codex-lb",
                        "defaultModel": "saved-default",
                        "retry": {"enabled": False},
                        "compaction": {"enabled": False},
                    }
                )
            )
            binary = root / "bin"
            binary.mkdir()
            helper = binary / "our-free-model-key"
            helper.write_text("#!/bin/sh\nprintf 'FIXTURE_LOCAL_KEY\\n'\n")
            helper.chmod(0o700)
            state = root / "state"
            (state / "our-free-model").mkdir(parents=True)
            (state / "our-free-model/settings.json").write_text(
                json.dumps({"standalonePort": server.server_port})
            )
            case = root / "case.json"
            plan_file = root / "plans.json"
            env = dict(
                isolated_environment(),
                HOME=str(root),
                PI_CODING_AGENT_DIR=str(agent),
                XDG_STATE_HOME=str(state),
                PATH=f"{binary}:{os.environ['PATH']}",
                PI_CACHE_CASE=str(case),
            )
            subagents = (
                ROOT
                / "home-manager/modules/ai/pi-base/extensions/interactive-subagents/pi-extension/subagents"
            )
            for model in ("kilo-free/kilo-auto/free", "opencode/deepseek-v4.1-flash-free"):
                case.write_text(
                    json.dumps(
                        {"subagentsDir": str(subagents), "planFile": str(plan_file), "model": model}
                    )
                )
                result = subprocess.run(
                    [
                        require_pi(),
                        "--offline",
                        "--no-extensions",
                        "--no-context-files",
                        "--no-skills",
                        "--no-prompt-templates",
                        "--no-mcp",
                        "--no-session",
                        "--model",
                        model,
                        "-e",
                        str(EXTENSION),
                        "-e",
                        str(ROOT / "tests/pi-codex-cache/child-launch.ts"),
                        "--mode",
                        "rpc",
                    ],
                    input="",
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                for plan in json.loads(plan_file.read_text()):
                    self.assertEqual(plan["loadout"]["model"], model)
                    self.assertIn(f"'{EXTENSION}'", plan["parts"])
                    self.assertIn("--no-extensions", plan["parts"])
                    result = subprocess.run(
                        [
                            "bash",
                            "-c",
                            " ".join(plan["parts"])
                            + " --offline --no-context-files --no-skills --no-prompt-templates --no-mcp --mode json --print",
                        ],
                        cwd=root,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn("Failed to load extension", result.stderr)
                    events = [
                        json.loads(line)
                        for line in result.stdout.splitlines()
                        if line.startswith("{")
                    ]
                    messages = [
                        e["message"]
                        for e in events
                        if e.get("type") == "message_end"
                        and e.get("message", {}).get("role") == "assistant"
                    ]
                    self.assertTrue(messages, result.stderr + result.stdout)
                    self.assertEqual(messages[-1]["stopReason"], "stop", messages[-1])
                    self.assertEqual(messages[-1]["content"][0]["text"], "FREE_CHILD_OK")
                    path, headers, body = server.requests[-1]
                    self.assertEqual(path, "/v1/chat/completions")
                    self.assertEqual(headers["Authorization"], "Bearer FIXTURE_LOCAL_KEY")
                    self.assertEqual(body["model"], model.split("/", 1)[1])
                    self.assertEqual(
                        {t["function"]["name"] for t in body["tools"]}, {"read", "ask_question"}
                    )
            self.assertEqual(len(server.requests), 4)

    def test_first_run_settings_are_private_and_later_edits_are_preserved(self):
        module = (ROOT / "home-manager/modules/ai/our-free-model.nix").read_text()
        seed = textwrap.dedent(
            module.split("\"our-free-model-initialize.py\" ''\n", 1)[1].split("\n  '';", 1)[0]
        )
        with tempfile.TemporaryDirectory(prefix="pi-proxy-seed-") as temporary:
            directory = Path(temporary) / "data"
            source = seed.replace("${builtins.toJSON dataDir}", repr(str(directory)))
            exec(compile(source, "our-free-model-initialize.py", "exec"), {})
            settings = directory / "settings.json"
            value = json.loads(settings.read_text())
            self.assertEqual(settings.stat().st_mode & 0o777, 0o600)
            self.assertEqual(value["distribution"], "managed")
            self.assertFalse(value["standaloneLanEnabled"])
            self.assertFalse(value["tokenSaver"]["enabled"])
            self.assertFalse(value["localOptimize"]["enabled"])
            settings.write_text('{"forwardKey":"FIXTURE_EXISTING_KEY"}')
            before = settings.read_bytes()
            exec(compile(source, "our-free-model-initialize.py", "exec"), {})
            self.assertEqual(settings.read_bytes(), before)

    def test_native_registration_replaces_paid_catalog_and_preserves_configuration(self):
        with tempfile.TemporaryDirectory(prefix="pi-local-proxy-") as temporary:
            root = Path(temporary)
            agent = root / "agent"
            agent.mkdir()
            settings = agent / "settings.json"
            settings.write_text(
                json.dumps({"defaultProvider": "codex-lb", "defaultModel": "saved"})
            )
            models = agent / "models.json"
            models.write_text("{}\n")
            before = (settings.read_bytes(), models.read_bytes())
            binary = root / "bin"
            binary.mkdir()
            helper = binary / "our-free-model-key"
            helper.write_text("#!/bin/sh\nprintf 'FIXTURE_LOCAL_KEY\\n'\n")
            helper.chmod(0o700)
            inspector = root / "inspect.ts"
            result_file = root / "providers.json"
            inspector.write_text(
                "import {writeFileSync} from 'node:fs';\n"
                "export default function(pi) { pi.on('session_start', async (_,ctx) => {\n"
                "writeFileSync(process.env.PROXY_FIXTURE_OUTPUT, JSON.stringify(\n"
                "ctx.modelRegistry.getAll().filter(m => ['opencode','kilo-free'].includes(m.provider))));\n"
                "}); }\n"
            )
            state = root / "state"
            (state / "our-free-model").mkdir(parents=True)
            (state / "our-free-model/settings.json").write_text('{"standalonePort":18901}')
            env = dict(
                isolated_environment(),
                HOME=str(root),
                PI_CODING_AGENT_DIR=str(agent),
                XDG_STATE_HOME=str(state),
                PATH=f"{binary}:{os.environ['PATH']}",
                PROXY_FIXTURE_OUTPUT=str(result_file),
            )
            args = [
                require_pi(),
                "--offline",
                "--no-extensions",
                "--no-context-files",
                "--no-skills",
                "--no-prompt-templates",
                "--no-mcp",
                "--no-session",
                "-e",
                str(EXTENSION),
            ]
            result = subprocess.run(
                args + ["--list-models"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("Failed to load extension", result.stderr)
            lines = [line.split() for line in result.stdout.splitlines()]
            rows = [row for row in lines if row and row[0] in ("opencode", "kilo-free")]
            self.assertEqual(sum(row[0] == "opencode" for row in rows), 8)
            self.assertEqual(sum(row[0] == "kilo-free" for row in rows), 3)
            self.assertNotIn("jev-1.13-free", result.stdout)
            self.assertNotIn("claude-opus", result.stdout)
            self.assertEqual((settings.read_bytes(), models.read_bytes()), before)
            # RPC startup inspects metadata without sending a model request.
            result = subprocess.run(
                args + ["-e", str(inspector), "--mode", "rpc"],
                input="",
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            registered = json.loads(result_file.read_text())
            self.assertEqual(len(registered), 11)
            self.assertTrue(all(m["baseUrl"] == "http://127.0.0.1:18901/v1" for m in registered))
            self.assertTrue(all(m["api"] == "openai-completions" for m in registered))
            self.assertTrue(all(m["maxTokens"] == 32768 for m in registered))


if __name__ == "__main__":
    unittest.main()
