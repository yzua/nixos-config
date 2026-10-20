import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { ChildLaunch } from "../pi-extension/subagents/child-launch.ts";
import { __test__ } from "../pi-extension/subagents/index.ts";
import { isSubagentLoadout, readSubagentLoadout } from "../pi-extension/subagents/session.ts";
import { createStatusState } from "../pi-extension/subagents/status.ts";
import { currentProfilePolicy } from "../pi-extension/subagents/profile-policy.ts";
import type { RunningSubagent } from "../pi-extension/subagents/managed-run.ts";

for (const profile of ["pi-base", "pi-home", "pi-re"] as const) {
  test(`${profile}: initial/resumed/nested workers retain policy and reject project discovery`, (t) => {
    const root = mkdtempSync(join(tmpdir(), "pi-profile-policy-"));
    const previous = {
      policy: process.env.PI_BASE_CHILD_POLICY,
      profile: process.env.PI_PROFILE,
      cwd: process.cwd(),
    };
    t.after(() => {
      for (const [name, value] of [
        ["PI_BASE_CHILD_POLICY", previous.policy],
        ["PI_PROFILE", previous.profile],
      ]) {
        if (value === undefined) delete process.env[name!];
        else process.env[name!] = value;
      }
      process.chdir(previous.cwd);
      rmSync(root, { recursive: true, force: true });
    });
    const instructions = join(root, "instructions.md");
    writeFileSync(instructions, "ORIGIN_INSTRUCTIONS");
    const agentDir = join(root, "agent");
    const workspace = join(root, "project");
    mkdirSync(join(workspace, ".pi/agent"), { recursive: true });
    mkdirSync(join(workspace, ".pi/agents"), { recursive: true });
    writeFileSync(join(workspace, ".pi/agents/poison.md"), "---\nname: poison\n---\nUNREVIEWED");
    process.chdir(workspace);
    const policy = {
      profile,
      pi: "/pinned/native-pi",
      agentDir,
      sessions: join(root, profile, "interactive-subagents/sessions"),
      instructions: [instructions],
      skills: [join(root, "skill")],
      extensions: [join(root, "common.ts")],
    };
    process.env.PI_PROFILE = profile;
    process.env.PI_BASE_CHILD_POLICY = JSON.stringify(policy);
    const child = new ChildLaunch(root, () => undefined);
    const running: RunningSubagent = {
      id: "fixture",
      name: "fixture",
      agent: "worker",
      task: "Approved task",
      surface: "%1",
      startTime: 0,
      sessionFile: join(root, "worker.jsonl"),
      parentArtifactDir: root,
      interactive: false,
      statusState: createStatusState({ source: "pi", startTimeMs: 0 }),
    };
    const plan = child.prepare(
      {
        kind: "initial",
        profile: {
          tools: "read,web_search,web_fetch",
          body: "ROLE_INSTRUCTIONS",
          systemPromptMode: "append",
        },
        cwd: workspace,
        agentDir,
      },
      running,
    );
    assert.equal(plan.kind, "pi");
    if (plan.kind !== "pi") throw new Error("Expected native Pi plan");
    assert.deepEqual(readSubagentLoadout(running.sessionFile)?.profilePolicy, policy);
    assert.equal(plan.parts[0], "'/pinned/native-pi'");
    for (const flag of [
      "--no-approve",
      "--no-context-files",
      "--no-extensions",
      "--no-skills",
      "--offline",
      "--no-mcp",
    ])
      assert.ok(plan.parts.includes(flag));
    assert.equal(plan.parts.filter((part) => part === "--append-system-prompt").length, 1);
    const prompt = plan.parts[plan.parts.indexOf("--append-system-prompt") + 1].slice(1, -1);
    assert.match(readFileSync(prompt, "utf8"), /ORIGIN_INSTRUCTIONS[\s\S]*ROLE_INSTRUCTIONS/);
    const resolved = __test__.resolveSubagentPaths({ cwd: workspace, task: "task" }, null);
    assert.equal(resolved.localAgentDir, null);
    assert.equal(resolved.effectiveAgentDir, policy.agentDir);
    assert.ok(
      __test__.getDefaultSessionDirFor(workspace, agentDir).startsWith(policy.sessions + "/"),
    );
    assert.ok(__test__.agentCatalog.listVisible().every((agent) => agent.source !== "project"));
    // A different requesting parent must not reinterpret the stored worker loadout.
    process.env.PI_BASE_CHILD_POLICY = JSON.stringify({
      ...policy,
      profile: "pi-base",
      sessions: join(root, "different"),
    });
    const resumed = child.prepare({ kind: "resume", loadout: plan.loadout }, running);
    assert.equal(resumed.kind, "pi");
    if (resumed.kind !== "pi") throw new Error("Expected resume plan");
    assert.deepEqual(resumed.loadout.profilePolicy, policy);
    assert.deepEqual(resumed.loadout.toolAllowlist, plan.loadout.toolAllowlist);
    assert.equal(
      isSubagentLoadout({ ...plan.loadout, profilePolicy: { ...policy, pi: "relative" } }),
      false,
    );
    // An agentless domain worker still has an explicit, replayable tool boundary.
    process.env.PI_BASE_CHILD_POLICY = JSON.stringify(policy);
    const agentless = child.prepare(
      { kind: "initial", profile: null, cwd: workspace, agentDir },
      running,
    );
    assert.equal(agentless.kind, "pi");
    if (agentless.kind === "pi")
      assert.ok(agentless.loadout.toolAllowlist?.includes("subagent_message"));
    assert.deepEqual(currentProfilePolicy(), policy);
    assert.throws(
      () =>
        child.prepare(
          { kind: "initial", profile: { cli: "claude" }, cwd: workspace, agentDir },
          running,
        ),
      /require Pi/,
    );
  });
}
