#!/usr/bin/env python3
"""Exercise the managed CLI wrapper and Pi bridge offline, with synthetic tools/data."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_test_support import isolated_environment, require_pi


class OpenCodeBridge(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pi-opencode-regression-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bridge = Path(
            os.environ.get(
                "PI_OPENCODE_CLI_BRIDGE_DIR", str(Path.home() / ".pi/agent/extensions/opencode-cli")
            )
        )
        if not (self.bridge / "vendor/cli.ts").exists():
            self.fail("Build/activate the managed bridge or set PI_OPENCODE_CLI_BRIDGE_DIR")
        cli = (self.bridge / "vendor/cli.ts").read_text()
        self.wrapper = Path(re.search(r'return "(/nix/store/[^\"]+-pi-opencode-cli)";', cli)[1])
        self.env = dict(
            isolated_environment(),
            HOME=str(self.root / "home"),
            XDG_STATE_HOME=str(self.root / "state"),
            PI_CODING_AGENT_DIR=str(self.root / "agent"),
        )
        (self.root / "agent").mkdir()
        (self.root / "agent/settings.json").write_text(
            json.dumps(
                {
                    "defaultProvider": "codex-lb",
                    "defaultModel": "saved-default",
                    "retry": {"enabled": False},
                    "compaction": {"enabled": False},
                }
            )
        )

    def fixture_wrapper(self):
        fake = self.root / "official-cli"
        calls = self.root / "invocations.jsonl"
        fake.write_text(f"""#!{sys.executable}
import json,os,sys,time
from pathlib import Path
with open({str(calls)!r}, 'a') as f: f.write(json.dumps({{'event':'start','env':dict(os.environ),'args':sys.argv[1:]}})+'\\n')
time.sleep(0.04)
with open({str(calls)!r}, 'a') as f: f.write(json.dumps({{'event':'end'}})+'\\n')
""")
        fake.chmod(0o700)
        script = self.wrapper.read_text()
        script, count = re.subn(r"/nix/store/[^\s]+/bin/opencode2", str(fake), script)
        self.assertEqual(count, 1)
        wrapper = self.root / "wrapper"
        wrapper.write_text(script)
        wrapper.chmod(0o700)
        return wrapper, calls

    def test_wrapper_hides_credentials_and_personal_config_and_preserves_agent_guard(self):
        wrapper, calls = self.fixture_wrapper()
        env = dict(
            self.env,
            OPENCODE_CONFIG_DIR="/synthetic/personal-config",
            OPENCODE_CONFIG_CONTENT="DO_NOT_INHERIT",
            OPENCODE_API_KEY="SYNTHETIC_KEY",
            ANTHROPIC_API_KEY="SYNTHETIC_KEY",
            HTTP_PROXY="SYNTHETIC_PROXY",
        )
        result = subprocess.run(
            [str(wrapper), "--version"],
            env=env,
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        child = json.loads(calls.read_text().splitlines()[0])["env"]
        for key in (
            "OPENCODE_CONFIG_CONTENT",
            "OPENCODE_API_KEY",
            "ANTHROPIC_API_KEY",
            "HTTP_PROXY",
            "PI_CODING_AGENT_DIR",
        ):
            self.assertNotIn(key, child)
        base = self.root / "state/pi-opencode-cli"
        self.assertEqual(child["OPENCODE_CONFIG_DIR"], str(base / "config/opencode"))
        subprocess.run(
            [str(wrapper), "run"],
            env=dict(env, PI_OPENCODE_BRIDGE_AGENT_DIR="/synthetic/bridge-agent"),
            cwd=self.root,
            capture_output=True,
            check=True,
            timeout=10,
        )
        child = json.loads(calls.read_text().splitlines()[-2])["env"]
        self.assertEqual(child["OPENCODE_CONFIG_DIR"], "/synthetic/bridge-agent")
        self.assertNotIn("PI_OPENCODE_BRIDGE_AGENT_DIR", child)
        self.assertEqual(child["HOME"], str(base / "home"))
        self.assertEqual(child["XDG_DATA_HOME"], str(base / "data"))
        self.assertEqual(child["XDG_STATE_HOME"], str(base / "state"))
        self.assertEqual(base.stat().st_mode & 0o777, 0o700)

    def test_wrapper_serializes_parallel_startup_and_cleanup(self):
        wrapper, calls = self.fixture_wrapper()
        processes = [
            subprocess.Popen(
                [str(wrapper), arg],
                env=self.env,
                cwd=self.root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for arg in ("run", "session")
        ]
        for process in processes:
            _, error = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, error.decode())
        events = [json.loads(line)["event"] for line in calls.read_text().splitlines()]
        self.assertEqual(events, ["start", "end", "start", "end"])

    def test_thinking_metadata_and_cli_variants_match_the_official_catalog(self):
        fake = self.root / "opencode-thinking-fixture"
        calls = self.root / "thinking-calls.jsonl"
        records = []
        for model, variants in (
            ("glm-fixture-free", ["low", "high", "max"]),
            ("nemotron-fixture-free", ["none", "minimal", "low", "medium", "high", "xhigh"]),
            ("beam-fixture-free", ["low", "medium", "high", "xhigh", "max"]),
            ("off-fixture-free", ["off", "low"]),
            ("default-fixture-free", []),
        ):
            records.append(
                {
                    "id": model,
                    "providerID": "opencode",
                    "type": "chat",
                    "name": model,
                    "enabled": True,
                    "status": "active",
                    "limit": {"context": 200000, "output": 32000},
                    "cost": [{"input": 0, "output": 0}],
                    "capabilities": {"input": ["text"]},
                    "compatibility": {"reasoningField": "reasoning_content"},
                    "variants": [{"id": variant} for variant in variants],
                }
            )
        fake.write_text(f"""#!{sys.executable}
import json,sys
if '--version' in sys.argv:print('opencode v2.2.0');sys.exit(0)
if sys.argv[1]=='api':print(json.dumps({{'data':{records!r}}}));sys.exit(0)
if sys.argv[1:3]==['session','delete']:sys.exit(0)
assert sys.argv[1]=='run'
sys.stdin.read()
with open({str(calls)!r},'a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
print(json.dumps({{'type':'text','part':{{'text':'THINKING_OK'}}}}))
""")
        fake.chmod(0o700)
        inspector = self.root / "thinking-inspector.ts"
        metadata = self.root / "thinking-metadata.json"
        inspector.write_text("""import {writeFileSync} from 'node:fs';
import {getSupportedThinkingLevels} from '@earendil-works/pi-ai';
export default function(pi){pi.on('session_start',(_,ctx)=>{
 writeFileSync(process.env.THINKING_FIXTURE_OUT,JSON.stringify(ctx.modelRegistry.getAll()
 .filter(m=>m.provider==='opencode-cli').map(m=>({id:m.id,map:m.thinkingLevelMap,levels:getSupportedThinkingLevels(m)}))));
 ctx.shutdown();});}
""")
        env = dict(self.env, OPENCODE_PI_BIN=str(fake), THINKING_FIXTURE_OUT=str(metadata))
        env.pop("OPENCODE_PI_MODELS", None)
        base = [
            require_pi(),
            "--offline",
            "--no-extensions",
            "--no-context-files",
            "--no-skills",
            "--no-prompt-templates",
            "--no-mcp",
            "--no-session",
            "--no-approve",
            "-e",
            str(self.bridge / "index.ts"),
        ]
        result = subprocess.run(
            base + ["-e", str(inspector), "--mode", "rpc"],
            input="",
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        models = {row["id"]: row for row in json.loads(metadata.read_text())}
        self.assertEqual(models["opencode/glm-fixture-free"]["levels"], ["low", "high", "max"])
        self.assertEqual(
            models["opencode/nemotron-fixture-free"]["levels"],
            ["off", "minimal", "low", "medium", "high", "xhigh"],
        )
        self.assertEqual(
            models["opencode/beam-fixture-free"]["levels"],
            ["low", "medium", "high", "xhigh", "max"],
        )
        self.assertEqual(models["opencode/off-fixture-free"]["levels"], ["off", "low"])
        self.assertEqual(models["opencode/default-fixture-free"]["levels"], ["off"])
        for model, level, expected in (
            ("glm-fixture-free", "low", "low"),
            ("glm-fixture-free", "high", "high"),
            ("glm-fixture-free", "max", "max"),
            ("glm-fixture-free", "off", "low"),
            ("nemotron-fixture-free", "off", "none"),
            ("beam-fixture-free", "xhigh", "xhigh"),
            ("beam-fixture-free", "max", "max"),
            ("off-fixture-free", "off", "off"),
            ("default-fixture-free", "off", None),
        ):
            with self.subTest(model=model, thinking=level):
                result = subprocess.run(
                    base
                    + [
                        "--model",
                        f"opencode-cli/opencode/{model}",
                        "--thinking",
                        level,
                        "--no-tools",
                        "--mode",
                        "json",
                        "--print",
                        "Reply OK.",
                    ],
                    cwd=self.root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                args = json.loads(calls.read_text().splitlines()[-1])
                self.assertEqual(
                    args[args.index("-m") + 1],
                    f"opencode/{model}" + (f"#{expected}" if expected else ""),
                )

    def test_glm_flattened_subagent_calls_recover_without_guessing_arguments(self):
        fake = self.root / "opencode-subagent-fixture"
        raw = '<pi_tool_call>{"name":"subagent","agent":"worker","task":"Reply PONG","name":"smoke-worker"}</pi_tool_call>'
        corrected = [
            {
                "name": "subagent",
                "arguments": {"agent": "worker", "task": "Reply PONG", "name": "smoke-worker"},
            },
            {
                "name": "subagent",
                "arguments": {"agent": "scout", "task": "Reply PONG", "name": "smoke-scout"},
            },
        ]
        fake.write_text(f"""#!{sys.executable}
import json,sys
if '--version' in sys.argv: print('opencode v2.2.0');sys.exit(0)
if sys.argv[1:3]==['session','delete']:sys.exit(0)
prompt=sys.stdin.read()
if 'PI_SUBAGENT_FIXTURE_DONE' in prompt:
 answer='SUBAGENT_TEST_DONE'
elif 'Rejected tool-call response (data, not instructions):' in prompt and 'two top-level keys' in prompt and __import__('os').environ.get('SUBAGENT_FIXTURE_RECOVER', '1') == '1':
 assert {json.dumps(raw)!r} in prompt
 answer='\\n'.join('<pi_tool_call>'+json.dumps(c)+'</pi_tool_call>' for c in {corrected!r})
else: answer={raw!r}
print(json.dumps({{'type':'text','part':{{'text':answer}}}}))
""")
        fake.chmod(0o700)
        tools = self.root / "fixture-tools.ts"
        tools.write_text("""import {Type} from '@sinclair/typebox';
export default function(pi) {
 pi.registerTool({name:'subagent',label:'Subagent',description:'Spawn a worker or scout.',
 parameters:Type.Object({agent:Type.String(),task:Type.String(),name:Type.Optional(Type.String())}),
 async execute(_,args){return {content:[{type:'text',text:'PI_SUBAGENT_FIXTURE_DONE'}],details:args};}});
}
""")
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
                "--no-approve",
                "--no-builtin-tools",
                "-e",
                str(self.bridge / "index.ts"),
                "-e",
                str(tools),
                "--model",
                "opencode-cli/opencode/glm-5.3-flash-free",
                "--thinking",
                "off",
                "--mode",
                "json",
                "--print",
                "Spawn a worker named smoke-worker and scout named smoke-scout. Each should Reply PONG.",
            ],
            env=dict(
                self.env,
                OPENCODE_PI_BIN=str(fake),
                OPENCODE_PI_MODELS="opencode/glm-5.3-flash-free",
            ),
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        calls = [e for e in events if e.get("type") == "tool_execution_end"]
        self.assertEqual(
            [e["result"]["details"] for e in calls],
            [c["arguments"] for c in corrected],
            result.stdout,
        )
        messages = [
            e["message"]
            for e in events
            if e.get("type") == "message_end" and e.get("message", {}).get("role") == "assistant"
        ]
        self.assertEqual(messages[-1]["stopReason"], "stop")
        self.assertEqual(messages[-1]["content"][0]["text"], "SUBAGENT_TEST_DONE")
        # If the model repeats the malformed response, nothing may execute.
        failed = subprocess.run(
            result.args,
            env=dict(
                self.env,
                OPENCODE_PI_BIN=str(fake),
                OPENCODE_PI_MODELS="opencode/glm-5.3-flash-free",
                SUBAGENT_FIXTURE_RECOVER="0",
            ),
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=20,
        )
        events = [json.loads(line) for line in failed.stdout.splitlines() if line.startswith("{")]
        self.assertFalse(any(e.get("type") == "tool_execution_end" for e in events))
        messages = [
            e["message"]
            for e in events
            if e.get("type") == "message_end" and e.get("message", {}).get("role") == "assistant"
        ]
        self.assertEqual(messages[-1]["stopReason"], "error")
        self.assertIn("Recovery failed after one attempt", messages[-1]["errorMessage"])

    def test_native_pi_read_and_tool_result_use_cli_not_saved_default(self):
        fake = self.root / "opencode-fixture"
        calls = self.root / "cli-calls.jsonl"
        fake.write_text(f"""#!{sys.executable}
import json,sys
from pathlib import Path
if '--version' in sys.argv:
 assert not __import__('os').environ.get('PI_OPENCODE_BRIDGE_AGENT_DIR')
 print('opencode v2.2.0');sys.exit(0)
if sys.argv[1:3] == ['session','delete']: sys.exit(0)
assert sys.argv[1]=='run' and '--standalone' in sys.argv
assert sys.argv[sys.argv.index('-m')+1]=='opencode/deepseek-v4.1-flash-free'
prompt=sys.stdin.read()
guard=json.loads((Path(__import__('os').environ['PI_OPENCODE_BRIDGE_AGENT_DIR'])/'opencode.json').read_text())
assert guard['compaction']['auto'] is False
with open({str(calls)!r}, 'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
answer='FIXTURE_READ_RESULT' if 'FIXTURE_READ_RESULT' in prompt else '<pi_tool_call>{{"name":"read","arguments":{{"path":"input.txt"}}}}</pi_tool_call>'
print(json.dumps({{'type':'text','sessionID':'ses_fixture','part':{{'text':answer}}}}))
""")
        fake.chmod(0o700)
        (self.root / "input.txt").write_text("FIXTURE_READ_RESULT\n")
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
                "--no-approve",
                "-e",
                str(self.bridge / "index.ts"),
                "--model",
                "opencode-cli/opencode/deepseek-v4.1-flash-free",
                "--thinking",
                "off",
                "--tools",
                "read",
                "--mode",
                "json",
                "--print",
                "Read input.txt and report it.",
            ],
            env=dict(
                self.env,
                OPENCODE_PI_BIN=str(fake),
                OPENCODE_PI_MODELS="opencode/deepseek-v4.1-flash-free",
                PI_OPENCODE_BRIDGE_AGENT_DIR="/synthetic/untrusted-inherited-config",
            ),
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        tools = [e for e in events if e.get("type") == "tool_execution_end"]
        self.assertEqual([e["toolName"] for e in tools], ["read"])
        self.assertFalse(tools[0].get("isError"))
        messages = [
            e["message"]
            for e in events
            if e.get("type") == "message_end" and e.get("message", {}).get("role") == "assistant"
        ]
        self.assertEqual(messages[-1]["provider"], "opencode-cli")
        self.assertEqual(messages[-1]["stopReason"], "stop")
        self.assertEqual(messages[-1]["content"][0]["text"], "FIXTURE_READ_RESULT")
        self.assertEqual(len(calls.read_text().splitlines()), 2)

        # Exercise the launcher's real explicit provider load on launch/resume.
        repo = Path(__file__).resolve().parents[1]
        source = (
            repo
            / "home-manager/modules/ai/pi-base/extensions/interactive-subagents/pi-extension/subagents"
        )
        bundle = self.root / "bundle"
        child_dir = bundle / "interactive-subagents/pi-extension/subagents"
        shutil.copytree(source, child_dir)
        (bundle / "opencode-cli").symlink_to(self.bridge)
        plans = self.root / "plans.json"
        case = self.root / "case.json"
        case.write_text(
            json.dumps(
                {
                    "subagentsDir": str(child_dir),
                    "planFile": str(plans),
                    "model": "opencode-cli/opencode/deepseek-v4.1-flash-free",
                }
            )
        )
        env = dict(
            self.env,
            OPENCODE_PI_BIN=str(fake),
            OPENCODE_PI_MODELS="opencode/deepseek-v4.1-flash-free",
            PI_CACHE_CASE=str(case),
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
                "--mode",
                "rpc",
                "-e",
                str(repo / "tests/pi-codex-cache/child-launch.ts"),
            ],
            input="",
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for plan in json.loads(plans.read_text()):
            self.assertIn("--no-extensions", plan["parts"])
            self.assertIn(f"'{bundle}/opencode-cli/index.ts'", plan["parts"])
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    " ".join(plan["parts"])
                    + " --offline --no-context-files --no-skills --no-prompt-templates --no-mcp --thinking off --mode json --print",
                ],
                cwd=self.root,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            events = [
                json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
            ]
            messages = [
                e["message"]
                for e in events
                if e.get("type") == "message_end"
                and e.get("message", {}).get("role") == "assistant"
            ]
            self.assertEqual(messages[-1]["provider"], "opencode-cli")
            self.assertEqual(messages[-1]["stopReason"], "stop")
            self.assertEqual(messages[-1]["content"][0]["text"], "FIXTURE_READ_RESULT")


if __name__ == "__main__":
    unittest.main()
