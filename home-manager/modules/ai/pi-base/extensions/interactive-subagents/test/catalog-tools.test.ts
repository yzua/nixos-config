/** Thin registered-tool checks; policy cases live at AgentCatalog's interface. */
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import extension from "../pi-extension/subagents/index.ts";

test("registered listing and spawn validation use the call-time catalog", async () => {
  const root = mkdtempSync(join(tmpdir(), "pi-catalog-tools-"));
  const previous = process.env.PI_CODING_AGENT_DIR;
  const tools = new Map<string, any>();
  try {
    process.env.PI_CODING_AGENT_DIR = root;
    const profiles = join(root, "agents");
    mkdirSync(profiles);
    writeFileSync(
      join(profiles, "catalog-visible-fixture.md"),
      "---\nname: catalog-visible-fixture\ndescription: Visible\nmodel: offline\n---\nIDENTITY",
    );
    writeFileSync(
      join(profiles, "catalog-hidden-fixture.md"),
      "---\nname: catalog-hidden-fixture\ndisable-model-invocation: true\n---\nHIDDEN",
    );
    extension({
      on() {},
      registerTool(tool: any) {
        tools.set(tool.name, tool);
      },
      registerCommand() {},
      registerMessageRenderer() {},
      registerShortcut() {},
    } as any);
    const list = await tools.get("subagents_list").execute();
    assert.match(list.content[0].text, /catalog-visible-fixture \[offline\] — Visible/);
    assert.doesNotMatch(list.content[0].text, /catalog-hidden-fixture/);
    assert.ok(list.details.agents.some((agent: any) => agent.name === "catalog-visible-fixture"));
    const unknown = await tools
      .get("subagent")
      .execute("unknown", { agent: "catalog-absent-fixture", task: "TASK" });
    assert.equal(unknown.details.error, "unknown agent");
    // This is a permission refusal, not a listing: hidden names remain in it.
    assert.match(unknown.content[0].text, /catalog-hidden-fixture/);
    // Never launch: the context explicitly has no persistent session. Whether
    // a mux exists or not, a hidden profile reaches prerequisite validation.
    const hidden = await tools
      .get("subagent")
      .execute("hidden", { agent: "catalog-hidden-fixture", task: "TASK" }, undefined, undefined, {
        sessionManager: { getSessionFile: () => null },
      });
    assert.notEqual(hidden.details.error, "unknown agent");
    assert.equal(hidden.details.id, undefined);
  } finally {
    if (previous === undefined) delete process.env.PI_CODING_AGENT_DIR;
    else process.env.PI_CODING_AGENT_DIR = previous;
    rmSync(root, { recursive: true, force: true });
  }
});
