import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { ChildLaunch, type AgentDefaults } from "../pi-extension/subagents/child-launch.ts";
import { readSubagentLoadout } from "../pi-extension/subagents/session.ts";
import { createStatusState } from "../pi-extension/subagents/status.ts";
import type { RunningSubagent } from "../pi-extension/subagents/managed-run.ts";

function fixture(t: { after(fn: () => void): void }) {
  const dir = mkdtempSync(join(tmpdir(), "pi-child-launch-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const extension = join(dir, "custom.ts");
  writeFileSync(extension, "// offline tool extension");
  const child = new ChildLaunch(dir, (tool) =>
    tool === "custom" || tool === "alias" ? extension : undefined,
  );
  const running: RunningSubagent = {
    id: "run",
    name: "Launch Test",
    task: "Do the task",
    agent: "fixture",
    surface: "%1",
    startTime: 0,
    sessionFile: join(dir, "child.jsonl"),
    parentArtifactDir: dir,
    interactive: false,
    statusState: createStatusState({ source: "pi", startTimeMs: 0 }),
  };
  const initial = (profile: AgentDefaults | null, model?: string) => {
    const plan = child.prepare(
      { kind: "initial", profile, model, cwd: dir, agentDir: dir },
      running,
    );
    assert.equal(plan.kind, "pi");
    if (plan.kind !== "pi") throw new Error("Expected Pi plan");
    assert.deepEqual(readSubagentLoadout(running.sessionFile), plan.loadout);
    return plan;
  };
  return { dir, child, running, initial, extension };
}
function unquote(arg: string): string {
  return arg.slice(1, -1).replace(/'\\''/g, "'");
}
function argFile(arg: string): string {
  return readFileSync(unquote(arg).replace(/^@/, ""), "utf8");
}

test("blank sessions hand off wrapped tasks and separated skill prompts; forks send only the task", (t) => {
  const { initial } = fixture(t);
  for (const sessionMode of ["standalone", "lineage-only", "fork"] as const) {
    const plan = initial({ sessionMode, skills: " review, ,lint ", body: "ROLE", autoExit: true });
    if (sessionMode === "fork") {
      assert.deepEqual(plan.parts.slice(-3), ["'/skill:review'", "'/skill:lint'", "'Do the task'"]);
    } else {
      assert.deepEqual(plan.parts.slice(-4, -1), ["''", "'/skill:review'", "'/skill:lint'"]);
      const task = argFile(plan.parts.at(-1)!);
      assert.match(task, /^\n\nROLE/);
      assert.match(task, /Complete your task autonomously/);
      assert.match(task, /Do the task/);
      assert.match(task, /Your FINAL assistant message should summarize/);
    }
  }
  const nonAuto = initial(null);
  assert.match(argFile(nonAuto.parts.at(-1)!), /The user can interact/);
  assert.match(argFile(nonAuto.parts.at(-1)!), /before the user exits/);
  assert.equal(nonAuto.autoExit, false);
  assert.ok(!nonAuto.parts.includes("''"), "no skill separator without skills");
});

test("tool restrictions, spawning grants, model and identity snapshot replay share one preparation interface", (t) => {
  const { initial, child, running, extension } = fixture(t);
  for (const mode of ["append", "replace"] as const) {
    const first = initial(
      {
        tools: " read,custom,alias,read ",
        subagentAgents: ["scout"],
        model: "profile-model",
        thinking: "medium",
        body: "IDENTITY",
        systemPromptMode: mode,
        autoExit: false,
      },
      "override-model",
    );
    assert.equal(
      first.loadout.toolAllowlist,
      "read,custom,alias,subagent,subagent_message,subagents_list,ask_question",
    );
    assert.equal(first.loadout.model, "override-model");
    assert.ok(first.parts.includes("--no-extensions"));
    assert.equal(first.parts.filter((arg) => arg === `'${extension}'`).length, 1);
    const flag = mode === "append" ? "--append-system-prompt" : "--system-prompt";
    assert.equal(argFile(first.parts[first.parts.indexOf(flag) + 1]), "IDENTITY");
    assert.ok(!argFile(first.parts.at(-1)!).includes("IDENTITY"));
    running.task = "Follow-up\nwith 'quotes'";
    const resume = child.prepare(
      { kind: "resume", loadout: readSubagentLoadout(running.sessionFile)! },
      running,
    );
    assert.equal(resume.kind, "pi");
    if (resume.kind !== "pi") throw new Error("Expected Pi plan");
    assert.deepEqual(resume.loadout, first.loadout);
    const firstSandbox = first.parts.slice(0, -1);
    const resumedSandbox = resume.parts.slice(0, -1);
    assert.equal(argFile(resumedSandbox[resumedSandbox.indexOf(flag) + 1]), "IDENTITY");
    // Each launch writes a fresh identity artifact; compare its content, not its timestamp.
    firstSandbox[firstSandbox.indexOf(flag) + 1] = "identity-artifact";
    resumedSandbox[resumedSandbox.indexOf(flag) + 1] = "identity-artifact";
    assert.deepEqual(resumedSandbox, firstSandbox);
    assert.equal(resume.autoExit, true, "saved manual initial policy never parks a resume");
    assert.equal(argFile(resume.parts.at(-1)!), running.task);
    assert.match(resume.scriptPreamble, /# Resume message file:/);
    assert.ok(resume.launchScriptFile.includes("-resume-"));
  }
});

test("unrestricted snapshots and reasoning without a model stay unrestricted on resume", (t) => {
  const { initial, child, running } = fixture(t);
  const first = initial({ sessionMode: "fork", thinking: "medium", skills: "review" });
  assert.equal(first.loadout.toolAllowlist, null);
  assert.ok(!first.parts.includes("--no-extensions"));
  assert.ok(!first.parts.includes("--tools"));
  assert.ok(!first.parts.includes("--model"));
  assert.ok(first.parts.includes("--thinking"));
  assert.deepEqual(first.parts.slice(-2), ["'/skill:review'", "'Do the task'"]);
  running.task = "";
  const resume = child.prepare({ kind: "resume", loadout: first.loadout }, running);
  assert.equal(resume.kind, "pi");
  if (resume.kind !== "pi") throw new Error("Expected Pi plan");
  assert.deepEqual(resume.parts, first.parts.slice(0, -2));
  assert.ok(!resume.scriptPreamble.includes("Resume message file"));
});

test("control tools accompany restrictions, while spawning requires an explicit grant", (t) => {
  const { initial } = fixture(t);
  assert.equal(
    initial({ tools: "read,bash,web_search" }).loadout.toolAllowlist,
    "read,bash,web_search,ask_question",
  );
  assert.equal(initial({ tools: "" }).loadout.toolAllowlist, null);
  assert.equal(initial({ subagentAgents: [] }).loadout.toolAllowlist, null);
  assert.equal(
    initial({ subagentAgents: ["scout"] }).loadout.toolAllowlist,
    "subagent,subagent_message,subagents_list,ask_question",
  );
  assert.equal(initial({ systemPromptMode: "replace" }).loadout.identity, null);
});

test("Claude keeps direct task, inline append identity, plugin, cwd and sentinel without Pi sandbox artifacts", (t) => {
  const { dir, child, running } = fixture(t);
  const plugin = join(dir, "plugin");
  mkdirSync(plugin);
  running.cli = "claude";
  running.sentinelFile = join(dir, "claude-done");
  const plan = child.prepare(
    {
      kind: "initial",
      profile: {
        cli: "claude",
        body: "ROLE",
        model: "profile-model",
        systemPromptMode: "replace",
        tools: "read",
        skills: "review",
      },
      model: "override",
      cwd: dir,
      agentDir: dir,
    },
    running,
  );
  assert.equal(plan.kind, "command");
  if (plan.kind !== "command") throw new Error("Expected Claude plan");
  assert.match(plan.command, /claude --dangerously-skip-permissions/);
  assert.ok(plan.command.startsWith(`cd '${dir}' && PI_CLAUDE_SENTINEL=`));
  assert.ok(plan.command.includes(`--plugin-dir '${plugin}'`));
  assert.ok(
    plan.command.includes("--model 'override' --append-system-prompt 'ROLE' 'Do the task'"),
  );
  assert.ok(!plan.command.includes("--tools"));
  assert.ok(!existsSync(`${running.sessionFile}.loadout.json`));
  assert.equal(dirname(plan.launchScriptFile), join(dir, "subagent-scripts"));
});
