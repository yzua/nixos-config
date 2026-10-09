/** Status policy is exercised through the production monitor and real sidecars. */
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { RunStatusMonitor, createStatusState } from "../pi-extension/subagents/status.ts";
import type { RunningSubagent } from "../pi-extension/subagents/managed-run.ts";
import type { SubagentActivityState } from "../pi-extension/subagents/activity.ts";

function fixture(
  run: (f: {
    monitor: RunStatusMonitor;
    child: RunningSubagent;
    publish: (fields?: Partial<SubagentActivityState>) => void;
    root: string;
  }) => void,
) {
  const root = mkdtempSync(join(tmpdir(), "pi-status-"));
  const child: RunningSubagent = {
    id: "child",
    name: "Worker",
    task: "TASK",
    surface: "%1",
    sessionFile: join(root, "child.jsonl"),
    parentArtifactDir: root,
    startTime: 0,
    interactive: false,
    activityFile: join(root, "activity.json"),
    statusState: createStatusState({ source: "pi", startTimeMs: 0 }),
  };
  const monitor = new RunStatusMonitor({ lineLimit: 4 });
  const publish = (fields: Partial<SubagentActivityState> = {}) =>
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
        ...fields,
      }),
    );
  try {
    run({ monitor, child, publish, root });
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

for (const problem of ["missing", "invalid", "wrong-id"] as const) {
  test(`${problem}: first observation starts the watchdog; repeated reads do not reset it`, () =>
    fixture(({ monitor, child, publish }) => {
      if (problem === "invalid") writeFileSync(child.activityFile!, "{invalid");
      if (problem === "wrong-id") publish({ runningChildId: "another-child" });
      // Equivalent to supervision before the optional notification timer starts.
      monitor.observe(child, 1000);
      assert.equal(child.activityRead?.reason, problem);
      if (problem === "invalid") assert.ok(child.activityRead?.error);
      assert.equal(monitor.snapshot(child, 60999).kind, "starting");
      const stalled = monitor.refresh([child], 61000);
      assert.equal(stalled.widgetChanged, true);
      assert.equal(monitor.snapshot(child, 61000).kind, "stalled");
      assert.equal(
        monitor.snapshot(child, 61000).statusLabel,
        problem === "wrong-id" ? "wrong activity id" : null,
      );
      assert.match(stalled.notification!.content, /Worker running 1m, stalled/);
      assert.equal(monitor.refresh([child], 62000).notification, null);
      publish({
        phase: "waiting",
        waitingSince: 63000,
        updatedAt: 63000,
        sequence: 2,
        latestEvent: "agent_end",
      });
      const recovered = monitor.refresh([child], 64000);
      assert.equal(recovered.widgetChanged, true);
      assert.deepEqual(recovered.notification?.lines, [
        "Worker running 1m, recovered; waiting 1s.",
      ]);
      assert.equal(monitor.refresh([child], 65000).notification, null);
    }));
}

test("active/waiting/done sidecars stay healthy without fresh writes; starting uses observation time", () =>
  fixture(({ monitor, child, publish }) => {
    publish();
    monitor.refresh([child], 5000);
    let snapshot = monitor.snapshot(child, 240000);
    assert.equal(snapshot.kind, "active");
    assert.equal(snapshot.activityLabel, "bash");
    assert.equal(snapshot.activeDurationText, "3m");
    assert.equal(monitor.refresh([child], 240000).notification, null);
    publish({
      phase: "waiting",
      updatedAt: 250000,
      waitingSince: 250000,
      latestEvent: "agent_end",
    });
    monitor.refresh([child], 250000);
    snapshot = monitor.snapshot(child, 500000);
    assert.equal(snapshot.kind, "waiting");
    assert.equal(snapshot.waitingDurationText, "4m");
    publish({ phase: "done", updatedAt: 500001, latestEvent: "agent_end" });
    monitor.observe(child, 500001);
    assert.equal(monitor.snapshot(child, 999999).statusLabel, "done");
    child.statusState = createStatusState({ source: "pi", startTimeMs: 0 });
    publish({ phase: "starting", updatedAt: 10, latestEvent: "session_start" });
    monitor.observe(child, 100000);
    assert.equal(monitor.snapshot(child, 159999).kind, "starting");
    assert.match(monitor.refresh([child], 160000).notification!.content, /stalled/);
  }));

test("transient loss keeps the healthy kind and the original problem clock; identical evidence recovers", () =>
  fixture(({ monitor, child, publish }) => {
    publish({ activeScope: "streaming" });
    monitor.refresh([child], 5000);
    rmSync(child.activityFile!);
    monitor.observe(child, 10000);
    assert.equal(monitor.snapshot(child, 20000).kind, "active");
    writeFileSync(child.activityFile!, "{}");
    assert.equal(monitor.refresh([child], 69999).notification, null);
    assert.match(monitor.refresh([child], 70000).notification!.content, /stalled 1m/);
    publish({ activeScope: "streaming" });
    assert.deepEqual(monitor.refresh([child], 71000).notification?.lines, [
      "Worker running 1m, recovered; active (streaming 1m).",
    ]);
    assert.equal(monitor.snapshot(child, 71000).snapshotError, null);
  }));

test("status fencing orders timestamps then sequences while retaining raw sidecar evidence", () =>
  fixture(({ monitor, child, publish }) => {
    publish({ updatedAt: 10000, sequence: 2 });
    monitor.observe(child, 10000);
    publish({ updatedAt: 9999, sequence: 99, phase: "waiting" });
    monitor.observe(child, 10001);
    assert.equal(monitor.snapshot(child, 10001).kind, "active");
    assert.equal(child.activity?.sequence, 99);
    publish({ updatedAt: 10000, sequence: 1, phase: "waiting" });
    monitor.observe(child, 10002);
    assert.equal(monitor.snapshot(child, 10002).kind, "active");
    publish({
      updatedAt: 10000,
      sequence: 3,
      phase: "waiting",
      waitingSince: 10000,
      latestEvent: "agent_end",
    });
    monitor.observe(child, 10003);
    assert.equal(monitor.snapshot(child, 11000).kind, "waiting");
    assert.equal(monitor.snapshot(child, 11000).latestEvent, "agent_end");
  }));

test("successful message delivery overrides locally; stale or exact-sequence evidence cannot undo it", () =>
  fixture(({ monitor, child, publish }) => {
    publish({ sequence: 2 });
    monitor.observe(child, 5000);
    // No messageDelivered operation on a failed send: observation alone preserves active status.
    monitor.observe(child, 20000);
    assert.equal(monitor.snapshot(child, 20000).kind, "active");
    monitor.messageDelivered(child, 20000);
    let snapshot = monitor.snapshot(child, 20000);
    assert.equal(snapshot.kind, "waiting");
    assert.equal(snapshot.activityLabel, "interrupted");
    assert.equal(snapshot.waitingDurationText, "0s");
    assert.equal(monitor.refresh([child], 21000).notification, null);
    for (const fields of [
      { updatedAt: 19999, sequence: 99 },
      { updatedAt: 20000, sequence: 2 },
      { updatedAt: 20000, sequence: 1 },
    ]) {
      publish(fields);
      monitor.observe(child, 22000);
      assert.equal(monitor.snapshot(child, 22000).activityLabel, "interrupted");
    }
    publish({ updatedAt: 20000, sequence: 3, activeScope: "streaming", activeSince: 20000 });
    monitor.observe(child, 23000);
    snapshot = monitor.snapshot(child, 23000);
    assert.equal(snapshot.kind, "active");
    assert.equal(snapshot.activityLabel, "streaming");
    monitor.messageDelivered(child, 24000);
    publish({ updatedAt: 25000, sequence: 1, activeScope: "provider", activeSince: 25000 });
    monitor.observe(child, 25000);
    assert.equal(monitor.snapshot(child, 25000).activityLabel, "provider");
  }));

test("activity labels translate scopes, including tool fallback", () =>
  fixture(({ monitor, child, publish }) => {
    for (const [scope, toolName, expected] of [
      ["tool", undefined, "tool"],
      ["tool", "write", "write"],
      ["provider", undefined, "provider"],
      ["streaming", undefined, "streaming"],
      ["turn", undefined, "turn"],
      ["agent", undefined, "agent"],
      [undefined, undefined, null],
    ] as const) {
      publish({ activeScope: scope, toolName });
      monitor.observe(child, 5000);
      assert.equal(monitor.snapshot(child, 5000).activityLabel, expected);
    }
  }));

test("Claude ignores activity and delivered-message overrides and never emits transitions", () =>
  fixture(({ monitor, child, publish }) => {
    child.cli = "claude";
    child.statusState = createStatusState({ source: "claude", startTimeMs: 0 });
    publish();
    monitor.observe(child, 1000);
    monitor.messageDelivered(child, 100000);
    assert.equal(child.activityRead, undefined);
    assert.equal(child.activity, undefined);
    assert.deepEqual(monitor.refresh([child], 125000), {
      widgetChanged: false,
      notification: null,
    });
    assert.equal(monitor.snapshot(child, 125000).kind, "running");
    assert.equal(monitor.snapshot(child, 125000).elapsedText, "2m");
  }));

test("interactive transitions change the widget but never wake the parent", () =>
  fixture(({ monitor, child, publish }) => {
    child.interactive = true;
    monitor.observe(child, 1000);
    assert.deepEqual(monitor.refresh([child], 61000), { widgetChanged: true, notification: null });
    publish({ updatedAt: 62000 });
    assert.deepEqual(monitor.refresh([child], 62000), { widgetChanged: true, notification: null });
    assert.equal(monitor.snapshot(child, 62000).kind, "active");
  }));

test("aggregate capping, bounded names/lines and recovery formatting are monitor outputs", () =>
  fixture(({ child, publish }) => {
    const monitor = new RunStatusMonitor({ lineLimit: 3 });
    const runs = Array.from({ length: 5 }, (_, i) => ({
      ...child,
      id: `child-${i}`,
      name: `Worker\n\n${"very-long-name-".repeat(12)}-${i}`,
      activityFile: undefined,
      statusState: createStatusState({ source: "pi", startTimeMs: 0 }),
    }));
    for (const run of runs) monitor.observe(run, 1000);
    const stalled = monitor.refresh(runs, 61000).notification!;
    assert.equal(stalled.lines.length, 3);
    assert.equal(stalled.overflow, 2);
    assert.match(stalled.content, /^Subagent status:\n• /);
    assert.match(stalled.content, /\+2 more running\./);
    assert.doesNotMatch(stalled.content, /\/tmp|\.jsonl/);
    for (const line of stalled.lines) {
      assert.doesNotMatch(line, /\n/);
      assert.ok(line.length <= 120);
    }
    runs[0].activityFile = child.activityFile;
    publish({ runningChildId: runs[0].id, updatedAt: 419000, activeSince: 419000 });
    const recovered = monitor.refresh(runs, 420000).notification!;
    assert.equal(recovered.lines.length, 1);
    assert.equal(recovered.overflow, 0);
    assert.match(recovered.lines[0], /running 7m, recovered; active \(bash 1s\)/);
    assert.ok(recovered.lines[0].length <= 120);
  }));
