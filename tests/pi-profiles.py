#!/usr/bin/env python3
"""Base inheritance, shared native configuration and profile-transition regressions."""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from pi_test_support import isolated_environment, require_pi, require_web_fetch_dependencies

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "home-manager/modules/ai/pi-base"
RE = ROOT / "home-manager/modules/ai/pi-re"
sys.path.insert(0, str(RE))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load("base_launcher", BASE / "launcher.py")
re = load("reviewed_launcher", RE / "launcher.py")


class ProfilePolicy(unittest.TestCase):
    def test_coding_retains_native_argv_and_deliberate_directory_overrides(self):
        config = {"profile": "pi-coding", "pi": "/pinned/pi", "agentDir": "/home/caller/.pi/agent"}
        args = [
            "--approve",
            "--extension",
            "custom.ts",
            "--session-dir",
            "/chosen",
            "--",
            "--prompt",
        ]
        self.assertEqual(base.pi_arguments(config, args), ["/pinned/pi", *args])
        env = base.profile_environment(
            config, {"HOME": "/home/caller", "PI_CODING_AGENT_DIR": "/explicit-role"}
        )
        self.assertEqual(env["PI_CODING_AGENT_DIR"], "/explicit-role")

    def test_transition_from_re_clears_domain_and_session_identity(self):
        config = {"profile": "pi-coding", "agentDir": "/home/caller/.pi/agent"}
        env = {
            "HOME": "/home/caller",
            "PI_PROFILE": "pi-re",
            "PI_RE_CONFIG": "/public/runtime.json",
            "PI_RE_CHILD": "1",
            "PI_CODING_AGENT_DIR": "/legacy/re-agent",
            "PI_CODING_AGENT_SESSION_DIR": "/home/caller/.local/state/pi-re/sessions",
            "PI_OFFLINE": "1",
            "KEEP": "unrelated",
        }
        actual = base.profile_environment(config, env)
        self.assertEqual(actual["PI_CODING_AGENT_DIR"], config["agentDir"])
        self.assertEqual(actual["PI_PROFILE"], "pi-coding")
        self.assertEqual(actual["KEEP"], "unrelated")
        self.assertFalse(any(key.startswith("PI_RE_") for key in actual))
        self.assertNotIn("PI_CODING_AGENT_SESSION_DIR", actual)
        self.assertNotIn("PI_OFFLINE", actual)
        self.assertEqual(env["PI_PROFILE"], "pi-re")

    def test_personal_history_is_private_and_cannot_alias_re_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sessions = root / "pi-home/sessions"
            base.private_session_directory(sessions)
            self.assertEqual(sessions.stat().st_mode & 0o777, 0o700)
            self.assertEqual(sessions.parent.stat().st_mode & 0o777, 0o700)
            sessions.rmdir()
            re_sessions = root / "pi-re/sessions"
            re_sessions.mkdir(parents=True)
            sessions.symlink_to(re_sessions, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlinks"):
                base.private_session_directory(sessions)
            self.assertFalse(any(re_sessions.iterdir()))

    def test_home_session_and_resource_overrides_are_guarded(self):
        for flag in ("--extension", "--skill", "--session-dir", "--approve", "--system-prompt"):
            with self.assertRaises(ValueError):
                base.checked_args([flag, "/foreign"], Path("/own/sessions"))
        self.assertEqual(
            base.checked_args(["--", "--extension"], Path("/own")), ["--", "--extension"]
        )


class NativeBase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pi-shared-profiles-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.agent = self.root / ".pi/agent"
        self.agent.mkdir(parents=True)
        self.env = {
            key: value
            for key, value in isolated_environment().items()
            if not key.startswith(("PI_", "XDG_")) and not key.endswith(("_API_KEY", "_TOKEN"))
        }
        self.env.update(
            HOME=str(self.root),
            XDG_STATE_HOME=str(self.root / "state"),
            XDG_DATA_HOME=str(self.root / "data"),
        )
        self.pi = require_pi()
        fetch = self.root / "web-fetch"
        fetch.mkdir()
        shutil.copyfile(BASE / "extensions/web-fetch/index.ts", fetch / "index.ts")
        (fetch / "node_modules").symlink_to(require_web_fetch_dependencies() / "node_modules")
        self.common = [
            str(BASE / "extensions" / file)
            for file in (
                "ask-user-question.ts",
                "network-diagnostics.ts",
                "codex-lb-session.ts",
                "upstream-retry.ts",
                "prompt-snippets/index.ts",
                "web-search/index.ts",
            )
        ]
        self.common.append(str(fetch / "index.ts"))
        self.common.append(
            str(BASE / "extensions/interactive-subagents/pi-extension/subagents/index.ts")
        )
        self.chrome = self.root / "pinned-skills/chrome-devtools-cli"
        self.chrome.mkdir(parents=True)
        (self.chrome / "SKILL.md").write_text(
            "---\nname: chrome-devtools-cli\ndescription: COMMON_BROWSER_FIXTURE\n---\nNo browser commands during discovery.\n"
        )
        global_chrome = self.agent / "skills/chrome-devtools-cli"
        global_chrome.mkdir(parents=True)
        (global_chrome / "SKILL.md").write_text(
            "---\nname: chrome-devtools-cli\ndescription: GLOBAL_BROWSER_FIXTURE\n---\nMutable global coding skill.\n"
        )
        unreviewed = self.agent / "skills/unreviewed"
        unreviewed.mkdir(parents=True)
        (unreviewed / "SKILL.md").write_text(
            "---\nname: unreviewed\ndescription: UNREVIEWED_GLOBAL_SKILL\n---\nDo not load in explicit profiles.\n"
        )
        self.instructions = self.root / "instructions.md"
        self.instructions.write_text("SHARED_BASE_INSTRUCTION\n")
        self.probe = self.root / "probe.mjs"
        self.probe.write_text(
            "import {ChildLaunch} from "
            + json.dumps(
                str(
                    BASE / "extensions/interactive-subagents/pi-extension/subagents/child-launch.ts"
                )
            )
            + ";\n"
            + """import {ModelRuntime, SettingsManager} from '@earendil-works/pi-coding-agent';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
export default function(pi) {
 pi.registerCommand('fixture-reload', {description:'Test native resource reload',handler:async(_,ctx)=>{await ctx.reload();}});
 pi.on('session_start', async (_,ctx)=> {
  const dir=process.env.PI_CODING_AGENT_DIR;
  const settings=SettingsManager.create(ctx.cwd,dir,{projectTrusted:false});
  if(process.env.FIXTURE_SAVE) {
   const runtime=await ModelRuntime.create({authPath:path.join(dir,'auth.json'), modelsPath:null, allowModelNetwork:false});
   await runtime.login(process.env.FIXTURE_AUTH_PROVIDER || 'openai','api_key',{prompt:async()=> 'SYNTHETIC_NATIVE_LOGIN',notify:()=>{}});
   settings.setDefaultModelAndProvider('openai','gpt-4.1');
   settings.setDefaultThinkingLevel('high');
   await settings.flush();
  }
  const snapshot={
   agent:dir, model:settings.getDefaultModel(), thinking:settings.getDefaultThinkingLevel(),
   hasBase:ctx.getSystemPrompt().includes('SHARED_BASE_INSTRUCTION'),
   hasRole:ctx.getSystemPrompt().includes('FIXTURE_SHARED_WORKER_ROLE'),
   tools:pi.getAllTools().map(t=>t.name), active:pi.getActiveTools(), commands:pi.getCommands().map(c=>c.name),
   modelProviders:[...new Set(ctx.modelRegistry.getAll().map(m=>m.provider))],
   browserSkills:pi.getCommands().filter(c=>c.name==='skill:chrome-devtools-cli').map(c=>c.description)
  };
  if(process.env.FIXTURE_CHILD) {
   const quote=s=>"'"+s.replaceAll("'", "'\\\\''")+"'";
   const source=process.env.FIXTURE_SUBAGENT_SOURCE;
   const running={id:'worker-fixture',name:'worker-fixture',agent:'worker',task:'Synthetic offline task',
     sessionFile:path.join(process.env.FIXTURE_ROOT,'worker.jsonl'),parentArtifactDir:process.env.FIXTURE_ROOT};
   const launcher=new ChildLaunch(source,()=>undefined);
   const initial=launcher.prepare({kind:'initial',profile:{tools:'read,web_search,web_fetch',body:'FIXTURE_SHARED_WORKER_ROLE',systemPromptMode:'append'},cwd:ctx.cwd,agentDir:dir},running);
   const resumed=launcher.prepare({kind:'resume',loadout:initial.loadout},running);
   snapshot.children=[];
   for(const plan of [initial,resumed]) {
    const policy=plan.loadout.profilePolicy;
    const env={...process.env,FIXTURE_CHILD:'',PI_PROFILE:policy.profile,PI_BASE_CHILD_POLICY:JSON.stringify(policy),PI_CODING_AGENT_SESSION_DIR:policy.sessions};
    for(const key of Object.keys(env)) if(key.startsWith('PI_RE_')) delete env[key];
    const command=plan.parts.join(' ')+' --extension '+quote(process.env.FIXTURE_PROBE)+' --no-session --print';
    const result=spawnSync('bash',['-c',command],{env,encoding:'utf8',timeout:15000});
    if(result.status!==0) throw new Error('Synthetic worker failed: '+result.stderr);
    const record=result.stdout.split('\\n').find(line=>line.startsWith('PROFILE_PROBE '));
    if(!record) throw new Error('Missing synthetic worker snapshot: '+result.stderr);
    snapshot.children.push(JSON.parse(record.slice('PROFILE_PROBE '.length)));
   }
  }
  if(process.env.FIXTURE_RELOAD && !process.env.FIXTURE_RELOADED) {
   process.env.FIXTURE_RELOADED='1';
   console.log('PROFILE_BEFORE '+JSON.stringify(snapshot));
   return;
  }
  console.log('PROFILE_PROBE '+JSON.stringify(snapshot));
  process.exit(0);
 });
}
"""
        )
        (self.agent / "settings.json").write_text(
            json.dumps(
                {
                    "defaultProvider": "openai",
                    "defaultModel": "gpt-4.1",
                    "defaultThinkingLevel": "low",
                    "defaultProjectTrust": "always",
                    "enableInstallTelemetry": False,
                    "extensions": ["+builtin:mcp"],
                    "sessionDir": str(self.root / "forbidden-history"),
                    "defaultTools": ["read"],
                }
            )
        )
        (self.agent / "auth.json").write_text("{}")
        # Hostile shared and project MCP/extension configuration must not run in explicit roots.
        self.poison = self.root / "poison-ran"
        command = {
            "command": sys.executable,
            "args": ["-c", f"open({str(self.poison)!r},'w').write('bad')"],
        }
        poison_config = json.dumps({"mcpServers": {"poison": command}})
        (self.agent / "mcp.json").write_text(poison_config)
        project = self.root / "workspace"
        (project / ".pi/extensions").mkdir(parents=True)
        (project / ".pi/mcp.json").write_text(poison_config)
        (project / "AGENTS.md").write_text("HOSTILE_PROJECT_CONTEXT")
        (project / ".pi/extensions/poison.mjs").write_text(
            f"import fs from 'node:fs'; export default()=>fs.writeFileSync({json.dumps(str(self.poison))},'bad');"
        )
        self.cwd = project
        self.mcp_before = (self.agent / "mcp.json").read_bytes()

    def launch(
        self,
        profile,
        *,
        save=False,
        child=False,
        auth_provider="openai",
        reload=False,
        children=False,
    ):
        sessions = self.root / "state" / profile / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        config = {
            "pi": self.pi,
            "profile": profile,
            "agentDir": str(self.agent),
            "sessions": str(sessions),
            "commonExtensions": self.common,
            "instructions": [str(self.instructions)],
            "skills": [str(self.chrome)]
            + (
                [str(ROOT / "home-manager/modules/ai/pi-home/skills/samsung-tv")]
                if profile == "pi-home"
                else []
            ),
        }
        if profile == "pi-re":
            config.update(resources=str(RE), commonSkills=[str(self.chrome)])
            locations = {"sessions": sessions}
            with patch.dict("os.environ", {"PI_RE_CHILD": "1" if child else "0"}):
                command = re.pi_arguments(config, locations, [])
        else:
            native = (
                ["--no-approve", "--no-context-files", "--no-mcp", "--session-dir", str(sessions)]
                if profile == "pi-coding"
                else []
            )
            command = base.pi_arguments(config, native)
        env = dict(self.env, PI_CODING_AGENT_DIR=str(self.agent), PI_PROFILE=profile)
        if profile != "pi-coding":
            env["PI_BASE_CHILD_POLICY"] = json.dumps(
                {
                    "profile": profile,
                    "pi": self.pi,
                    "agentDir": str(self.agent),
                    "sessions": str(sessions.parent / "interactive-subagents/sessions"),
                    "instructions": [str(self.instructions)],
                    "skills": config["skills"],
                    "extensions": self.common,
                }
            )
        if child:
            env["PI_RE_CHILD"] = "1"
        if children:
            env.update(
                FIXTURE_CHILD="1",
                FIXTURE_ROOT=str(self.root),
                FIXTURE_PROBE=str(self.probe),
                FIXTURE_SUBAGENT_SOURCE=str(
                    BASE / "extensions/interactive-subagents/pi-extension/subagents"
                ),
            )
        if reload:
            env["FIXTURE_RELOAD"] = "1"
        if save:
            env["FIXTURE_SAVE"] = "1"
            env["FIXTURE_AUTH_PROVIDER"] = auth_provider
        result = subprocess.run(
            [
                *command,
                "--extension",
                str(self.probe),
                "--no-session",
                "--print",
                "/fixture-reload" if reload else "probe",
            ],
            cwd=self.cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Failed to load extension", result.stderr)
        self.assertFalse(self.poison.exists(), result.stderr)
        self.assertFalse((self.root / "forbidden-history").exists())
        self.assertEqual((self.agent / "mcp.json").read_bytes(), self.mcp_before)
        lines = [
            line.removeprefix("PROFILE_PROBE ")
            for line in result.stdout.splitlines()
            if line.startswith("PROFILE_PROBE ")
        ]
        self.assertEqual(len(lines), 1, result.stdout + result.stderr)
        value = json.loads(lines[0])
        if reload:
            before = [
                json.loads(line.removeprefix("PROFILE_BEFORE "))
                for line in result.stdout.splitlines()
                if line.startswith("PROFILE_BEFORE ")
            ]
            self.assertEqual(len(before), 1, result.stdout + result.stderr)
            self.assertEqual(set(before[0]["active"]), set(value["active"]))
            self.assertEqual(set(before[0]["tools"]), set(value["tools"]))
        return value

    def test_native_shared_workers_keep_origin_instructions_and_toolsets_on_resume(self):
        for profile in ("pi-base", "pi-home", "pi-re"):
            value = self.launch(profile, children=True)
            self.assertEqual(len(value["children"]), 2)
            for worker in value["children"]:
                self.assertEqual(worker["agent"], str(self.agent))
                self.assertTrue(worker["hasBase"])
                self.assertTrue(worker["hasRole"])
                self.assertEqual(worker["browserSkills"], ["COMMON_BROWSER_FIXTURE"])
                if profile == "pi-home":
                    self.assertEqual(worker["commands"].count("skill:samsung-tv"), 1)
                self.assertTrue({"read", "web_search", "web_fetch"} <= set(worker["active"]))
                self.assertNotIn("bash", worker["active"])
                self.assertNotIn("subagent", worker["active"])
                for tool in ("web_search", "web_fetch"):
                    self.assertEqual(worker["tools"].count(tool), 1)

    def test_shared_browser_skill_is_selected_once_without_ambient_skill_discovery(self):
        for profile in ("pi-base", "pi-home", "pi-re", "pi-coding"):
            value = self.launch(profile)
            self.assertEqual(
                value["browserSkills"],
                ["GLOBAL_BROWSER_FIXTURE" if profile == "pi-coding" else "COMMON_BROWSER_FIXTURE"],
            )
            self.assertEqual("skill:unreviewed" in value["commands"], profile == "pi-coding")
            if profile == "pi-home":
                self.assertEqual(value["commands"].count("skill:samsung-tv"), 1)
        child = self.launch("pi-re", child=True)
        self.assertEqual(child["browserSkills"], [])

    def test_migrated_re_only_provider_is_visible_to_all_native_profiles(self):
        legacy = self.root / "data/pi-re/agent"
        legacy.mkdir(parents=True)
        (legacy / "models.json").write_text(
            json.dumps(
                {
                    "providers": {
                        "fixture-re": {
                            "api": "openai-completions",
                            "baseUrl": "https://fixture.invalid/v1",
                            "models": [
                                {
                                    "id": "fixture-flash",
                                    "name": "Fixture Flash",
                                    "reasoning": False,
                                    "input": ["text"],
                                    "cost": {
                                        "input": 0,
                                        "output": 0,
                                        "cacheRead": 0,
                                        "cacheWrite": 0,
                                    },
                                    "contextWindow": 2000,
                                    "maxTokens": 128,
                                }
                            ],
                        }
                    }
                }
            )
        )
        (legacy / "auth.json").write_text(
            json.dumps({"fixture-re": {"type": "api_key", "key": "SYNTHETIC-RE-ONLY"}})
        )
        with patch("builtins.print"):
            re.initialize(legacy, self.root / "state/pi-re", self.agent)
        for profile in ("pi-re", "pi-base", "pi-home", "pi-coding"):
            value = self.launch(profile)
            self.assertIn("fixture-re", value["modelProviders"])
            self.assertEqual(value["model"], "gpt-4.1")
        self.assertIn("fixture-re", json.loads((self.agent / "auth.json").read_text()))
        self.assertFalse((legacy / "auth.json").exists())

    def test_concurrent_root_logins_use_the_same_native_credential_store(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            home = pool.submit(self.launch, "pi-home", save=True, auth_provider="openai")
            neutral = pool.submit(self.launch, "pi-base", save=True, auth_provider="anthropic")
            self.assertEqual(home.result()["agent"], neutral.result()["agent"])
        auth = json.loads((self.agent / "auth.json").read_text())
        self.assertEqual(set(auth), {"openai", "anthropic"})
        self.assertFalse((self.agent / "auth.json").is_symlink())
        self.assertFalse((self.agent / "auth.json.lock").exists())

    def test_common_tools_commands_and_live_native_login_defaults_across_roots(self):
        first = self.launch("pi-home", save=True)
        self.assertEqual(first["thinking"], "high")
        for profile in ("pi-base", "pi-re", "pi-home"):
            value = self.launch(profile)
            self.assertEqual(value["agent"], str(self.agent))
            self.assertEqual(value["model"], "gpt-4.1")
            self.assertEqual(value["thinking"], "high")
            for tool in ("ask_user_question", "web_search", "web_fetch"):
                self.assertEqual(value["tools"].count(tool), 1)
                self.assertIn(tool, value["active"])
            self.assertTrue({"read", "bash", "edit", "write"} <= set(value["active"]))
            for command in ("net-debug", "snippets"):
                self.assertEqual(value["commands"].count(command), 1)
            for tool in ("subagent", "subagent_message", "subagents_list"):
                self.assertEqual(value["tools"].count(tool), 1)
                self.assertIn(tool, value["active"])
        coding = self.launch("pi-coding")
        self.assertEqual((coding["model"], coding["thinking"]), ("gpt-4.1", "high"))
        for preference in ([], ["+codemode", "+subagent"]):
            settings = json.loads((self.agent / "settings.json").read_text())
            settings["defaultTools"] = preference
            (self.agent / "settings.json").write_text(json.dumps(settings))
            child = self.launch("pi-re", child=True, reload=True)
            self.assertEqual(set(child["active"]), {"read", "bash", "edit", "write"})
            self.assertNotIn("ask_user_question", child["tools"])
            self.assertNotIn("web_search", child["tools"])
            self.assertNotIn("re_subagent", child["tools"])
            for profile in ("pi-home", "pi-base", "pi-re"):
                root = self.launch(profile, reload=True)
                self.assertTrue(
                    {"read", "bash", "ask_user_question", "web_search", "web_fetch"}
                    <= set(root["active"])
                )
                self.assertTrue(
                    {"subagent", "subagent_message", "subagents_list"} <= set(root["active"])
                )
        self.assertEqual(
            json.loads((self.agent / "auth.json").read_text())["openai"]["key"],
            "SYNTHETIC_NATIVE_LOGIN",
        )
        self.assertFalse(any((self.root / "data").rglob("auth.json")))


if __name__ == "__main__":
    unittest.main()
