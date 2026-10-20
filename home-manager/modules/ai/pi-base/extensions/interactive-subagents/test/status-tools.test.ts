/** Thin steering adapter check, run only by the closed offline loader. */
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import extension, { __test__ } from "../pi-extension/subagents/index.ts";
import { RunStatusMonitor, createStatusState } from "../pi-extension/subagents/status.ts";
import type { RunningSubagent } from "../pi-extension/subagents/managed-run.ts";

test("registered steering applies the monitor override only after a successful send", async () => {
  // Never risk running this fixture against a real caller's mux. The standard
  // offline runner supplies this private root and substitutes all mux operations.
  assert.ok(process.env.PI_RECALL_ROOT, "Use tests/pi-subagents-recall.test.mjs's closed loader");
  assert.ok(
    process.execArgv.some((arg) => arg.endsWith("/pi-subagents-recall/loader.mjs")),
    "The closed mux loader is required",
  );
  const previousRoot = process.env.PI_RECALL_ROOT;
  const root = mkdtempSync(join(previousRoot, "status-tools-"));
  const tools = new Map<string, any>();
  const monitor = new RunStatusMonitor({ lineLimit: 4 });
  const child: RunningSubagent = {
    id: "adapter",
    name: "Adapter",
    task: "TASK",
    surface: "%9901",
    sessionFile: join(root, "child.jsonl"),
    parentArtifactDir: root,
    startTime: 0,
    interactive: false,
    activityFile: join(root, "activity.json"),
    statusState: createStatusState({ source: "pi", startTimeMs: 0 }),
  };
  try {
    process.env.PI_RECALL_ROOT = root;
    writeFileSync(
      child.activityFile!,
      JSON.stringify({
        version: 1,
        runningChildId: child.id,
        createdAt: 0,
        updatedAt: 5000,
        sequence: 1,
        latestEvent: "tool_execution_start",
        phase: "active",
        agentActive: true,
        turnActive: true,
        providerActive: false,
        toolActive: true,
        activeScope: "tool",
        activeSince: 5000,
        toolName: "bash",
      }),
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
    // Seed only the run fixture; routing and status policy are exercised through
    // the registered tool, not orchestration helpers exported for tests.
    __test__.runningSubagents.set(child.id, child);
    const ctx = { sessionManager: { getSessionDir: () => root, getSessionId: () => "parent" } };
    const steer = () =>
      tools
        .get("subagent_message")
        .execute("steer", { name: child.name, message: "keep\ngoing" }, undefined, undefined, ctx);
    const failed = await steer(); // Fake surface does not exist yet.
    assert.match(failed.details.error, /Failed to deliver message/);
    assert.equal(monitor.snapshot(child, 20000).kind, "active");
    writeFileSync(
      join(root, `surface-${child.surface}.json`),
      JSON.stringify({ done: false, closed: false }),
    );
    const delivered = await steer();
    assert.equal(delivered.details.status, "steered");
    assert.equal(monitor.snapshot(child, Date.now()).kind, "waiting");
    assert.equal(monitor.snapshot(child, Date.now()).latestEvent, "interrupt_requested");
    assert.equal(__test__.runningSubagents.get(child.id), child);
  } finally {
    __test__.runningSubagents.delete(child.id);
    process.env.PI_RECALL_ROOT = previousRoot;
    rmSync(root, { recursive: true, force: true });
  }
});
