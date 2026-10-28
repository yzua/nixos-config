// Prepare the real restricted coding child command without launching a terminal pane.
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { ChildLaunch } from "../../home-manager/modules/ai/pi-base/extensions/interactive-subagents/pi-extension/subagents/child-launch.ts";
import { createStatusState } from "../../home-manager/modules/ai/pi-base/extensions/interactive-subagents/pi-extension/subagents/status.ts";
import type { RunningSubagent } from "../../home-manager/modules/ai/pi-base/extensions/interactive-subagents/pi-extension/subagents/managed-run.ts";

export default function (pi: ExtensionAPI) {
  pi.on("session_start", (_event, ctx) => {
    const testCase = JSON.parse(readFileSync(process.env.PI_CACHE_CASE!, "utf8"));
    const running: RunningSubagent = {
      id: "cache-child",
      name: "Cache child",
      agent: "fixture",
      task: "Synthetic child fixture",
      surface: "%fixture",
      startTime: 0,
      sessionFile: join(ctx.cwd, "restricted-child.jsonl"),
      parentArtifactDir: ctx.cwd,
      interactive: false,
      statusState: createStatusState({ source: "pi", startTimeMs: 0 }),
    };
    const child = new ChildLaunch(testCase.subagentsDir, () => undefined);
    const initial = child.prepare(
      {
        kind: "initial",
        profile: { tools: "read", model: testCase.model ?? "codex-lb/fixture", autoExit: true },
        cwd: ctx.cwd,
        agentDir: process.env.PI_CODING_AGENT_DIR!,
      },
      running,
    );
    if (initial.kind !== "pi") throw new Error("Expected Pi child");
    running.task = "Synthetic resumed child fixture";
    const resumed = child.prepare({ kind: "resume", loadout: initial.loadout }, running);
    writeFileSync(testCase.planFile, JSON.stringify([initial, resumed]));
    ctx.shutdown();
  });
}
