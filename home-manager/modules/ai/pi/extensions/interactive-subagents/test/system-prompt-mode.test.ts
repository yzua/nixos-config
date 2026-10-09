/** Identity routing exercises production parsing and launch preparation. */
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { __test__ } from "../pi-extension/subagents/index.ts";
import { ChildLaunch } from "../pi-extension/subagents/child-launch.ts";
import { createStatusState } from "../pi-extension/subagents/status.ts";

for (const mode of ["replace", "append", undefined, "invalid"] as const) {
  test(`production profile parsing and identity routing: ${mode}`, () => {
    const root = mkdtempSync(join(tmpdir(), "pi-system-prompt-"));
    const previousDir = process.env.PI_CODING_AGENT_DIR;
    const previousCwd = process.cwd();
    try {
      // Only private project/global directories are discoverable during this test.
      process.chdir(root);
      process.env.PI_CODING_AGENT_DIR = join(root, "agent");
      const agents = join(root, ".pi", "agents");
      mkdirSync(agents, { recursive: true });
      writeFileSync(
        join(agents, "identity-fixture.md"),
        `---\nmodel: offline-model\n${mode ? `system-prompt: ${mode}\n` : ""}---\nIDENTITY`,
      );
      const profile = __test__.loadAgentDefaults("identity-fixture");
      assert.ok(profile);
      const expected = mode === "append" || mode === "replace" ? mode : undefined;
      assert.equal(profile.systemPromptMode, expected);
      assert.equal(profile.body, "IDENTITY");
      const plan = new ChildLaunch(root, () => undefined).prepare(
        {
          kind: "initial",
          profile,
          cwd: null,
          agentDir: null,
        },
        {
          id: "identity-run",
          name: "Identity",
          task: "TASK",
          agent: "identity-fixture",
          surface: "%1",
          sessionFile: join(root, "child.jsonl"),
          parentArtifactDir: root,
          startTime: 0,
          interactive: true,
          statusState: createStatusState({ source: "pi", startTimeMs: 0 }),
        },
      );
      assert.equal(plan.kind, "pi");
      if (plan.kind !== "pi") throw new Error("Expected Pi plan");
      const task = readFileSync(plan.parts.at(-1)!.slice(2, -1), "utf8");
      assert.equal(task.includes("IDENTITY"), !expected);
      assert.equal(plan.loadout.identity, expected ? "IDENTITY" : null);
      if (expected)
        assert.ok(
          plan.parts.includes(
            expected === "replace" ? "--system-prompt" : "--append-system-prompt",
          ),
        );
      else
        assert.ok(
          !plan.parts.includes("--system-prompt") && !plan.parts.includes("--append-system-prompt"),
        );
    } finally {
      process.chdir(previousCwd);
      if (previousDir === undefined) delete process.env.PI_CODING_AGENT_DIR;
      else process.env.PI_CODING_AGENT_DIR = previousDir;
      rmSync(root, { recursive: true, force: true });
    }
  });
}
