// Exercises the real extension lifecycle and registered tool routing offline.
import assert from "node:assert/strict";
import { appendFileSync, existsSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { record } from "./mux.mjs";

const root = process.env.PI_RECALL_ROOT;
const source = new URL("../../home-manager/modules/ai/pi/extensions/interactive-subagents/pi-extension/subagents/index.ts", import.meta.url);
const file = (name) => join(root, name);
const json = (name) => JSON.parse(readFileSync(file(name), "utf8"));
const save = (name, value) => writeFileSync(file(name), JSON.stringify(value));
const calls = (op) => existsSync(file("calls.jsonl")) ? readFileSync(file("calls.jsonl"), "utf8").trim().split("\n").map(JSON.parse).filter((c) => c.op === op) : [];
const owner = (run) => JSON.parse(readFileSync(`${run.sessionFile}.owner.json`, "utf8"));
const setOwner = (run, value) => writeFileSync(`${run.sessionFile}.owner.json`, JSON.stringify(value));
const ctx = {
  cwd: root, hasUI: false,
  sessionManager: {
    getSessionFile: () => file("parent.jsonl"),
    getSessionDir: () => root,
    getSessionId: () => "parent-session",
  },
  ui: { notify: (...args) => record("warning", ...args), setWidget() {} },
};
async function runtime(tag) {
  const events = new Map(), tools = new Map(), messages = [];
  const pi = {
    on: (name, handler) => events.set(name, handler),
    registerTool: (tool) => tools.set(tool.name, tool),
    registerCommand() {}, registerMessageRenderer() {},
    sendMessage: (message) => { messages.push(message); record("result", tag, message); },
  };
  const module = await import(`${source.href}?runtime=${tag}`);
  module.default(pi);
  await events.get("session_start")({}, ctx);
  return { module, messages, stop: () => events.get("session_shutdown")({}, ctx),
    tool: (name, params) => tools.get(name).execute("offline-tool", params, new AbortController().signal, undefined, ctx) };
}
async function launch(rt) {
  const response = await rt.tool("subagent", { agent: "recall-fixture", name: "Recall", task: "original task" });
  assert.equal(response.details.status, "started");
  save("original.json", response.details);
  save("original-owner.json", owner(response.details));
  return response.details;
}
async function waitFor(predicate) {
  for (let i = 0; i < 200; i++) { if (predicate()) return; await delay(5); }
  assert.fail("offline completion timeout");
}
function finishSurface(run, text) {
  appendFileSync(run.sessionFile, JSON.stringify({ type: "message", message: { role: "assistant", content: [{ type: "text", text }] } }) + "\n");
  save(`surface-${owner(run).surface}.json`, { done: true, closed: false });
}
async function verifyRecall(rt, run) {
  const before = json("original-owner.json");
  const after = owner(run);
  assert.equal(after.token, before.token, "writer claim retained");
  assert.notEqual(after.supervisor, before.supervisor, "obsolete watcher fenced");
  for (const key of ["id", "name", "task", "startTime", "sessionFile", "activityFile", "surface", "agent", "interactive", "launchScriptFile"]) assert.deepEqual(after.run[key], before.run[key], key);
  assert.deepEqual(after.policy, before.policy);
  assert.deepEqual(after.loadout, before.loadout, "model/tools sandbox retained");
  assert.equal(rt.module.__test__.runningSubagents.size, 1);
  const response = await rt.tool("subagent_message", { name: "Recall", message: "active steer" });
  assert.equal(response.details.status, "steered");
  assert.equal(response.details.id, run.id);
  assert.equal(calls("steer").at(-1).args[0], before.surface);
  assert.equal(calls("spawn").length, 1, "active recall never spawns");
  assert.equal(calls("dispatch").length, 1);
  assert.equal(calls("close").length, 0, "disposed watcher did not close adopted child");
  assert.equal(rt.messages.length, 0);
}
async function verifyCompletionAndFollowup(rt, original) {
  finishSurface(original, "ORIGINAL_RESULT");
  await waitFor(() => rt.messages.length === 1);
  assert.equal(rt.messages[0].details.name, "Recall");
  assert.equal(rt.messages[0].details.task, "original task");
  assert.match(rt.messages[0].content, /ORIGINAL_RESULT/);
  assert.equal(owner(original).delivered, true);
  const completed = await runtime("completed-runtime");
  await delay(75);
  assert.equal(completed.messages.length, 0, "completion never replayed after another reload");
  assert.equal(calls("result").length, 1);
  const followup = await completed.tool("subagent_message", { name: "Recall", message: "new followup" });
  assert.equal(followup.details.status, "started");
  assert.equal(followup.details.name, "Recall");
  assert.equal(followup.details.sessionFile, original.sessionFile);
  assert.equal(followup.details.sessionId, "original-child-session");
  assert.notEqual(followup.details.id, original.id);
  assert.equal(calls("spawn").length, 2);
  assert.notEqual(owner(original).surface, json("original-owner.json").surface);
  const newPolicy = owner(original).policy;
  assert.equal(newPolicy.kind, "resume");
  assert.equal(newPolicy.entryCountBefore, 2, "old output excluded from followup");
  // Recall an active resumed run too: its baseline must not be resampled.
  const resumedOwner = owner(original);
  completed.stop();
  const resumed = await runtime("recalled-followup");
  assert.equal(owner(original).run.id, followup.details.id);
  assert.deepEqual(owner(original).policy, newPolicy);
  assert.deepEqual(owner(original).loadout, resumedOwner.loadout);
  const steered = await resumed.tool("subagent_message", { name: "Recall", message: "followup steer" });
  assert.equal(steered.details.status, "steered");
  assert.equal(calls("spawn").length, 2);
  finishSurface(followup.details, "FOLLOWUP_RESULT");
  await waitFor(() => resumed.messages.length === 1);
  assert.match(resumed.messages[0].content, /FOLLOWUP_RESULT/);
  assert.doesNotMatch(resumed.messages[0].content, /ORIGINAL_RESULT/);
  assert.equal(completed.messages.length, 0);
  assert.equal(calls("result").length, 2);
  resumed.stop(); rt.stop();
}

const mode = process.argv[2];
if (mode !== "restart-reader" && !mode.startsWith("cold-")) {
  mkdirSync(file("agent/agents"), { recursive: true });
  writeFileSync(file("agent/agents/recall-fixture.md"), "---\nname: recall-fixture\nmodel: offline-default\ntools: read,bash\nauto-exit: true\n---\nOffline identity.\n");
  writeFileSync(file("parent.jsonl"), JSON.stringify({ type: "session", version: 3, id: "parent-session" }) + "\n");
}
if (mode === "restart-writer") {
  const rt = await runtime("writer-process");
  await launch(rt);
  process.exit(0); // Deliberately no shutdown: durable state survives process death.
} else if (mode === "restart-reader") {
  const rt = await runtime("reader-process");
  const run = json("original.json");
  await verifyRecall(rt, run);
  await verifyCompletionAndFollowup(rt, run);
} else if (mode.startsWith("cold-")) {
  const original = json("original.json");
  const old = owner(original);
  const leaseFile = `${original.sessionFile}.writer.json`;
  const lease = JSON.parse(readFileSync(leaseFile, "utf8"));
  // Same public IDs/path/PID may be reused by a different mux server. Its pane
  // even contains a stale success sentinel: none of these prove writer death.
  save("incarnation.json", { dev: "1", ino: "99", ctimeNs: "100" });
  save(`surface-${old.surface}.json`, { done: true, closed: false });
  writeFileSync(`${original.sessionFile}.exit`, JSON.stringify({ type: "error", errorMessage: "STALE_ERROR" }));
  writeFileSync(`${original.sessionFile}.ask`, JSON.stringify({ question: "STALE_QUESTION" }));
  appendFileSync(original.sessionFile, JSON.stringify({ type: "message", message: { role: "assistant", content: [{ type: "text", text: "OLD_COLD_OUTPUT" }] } }) + "\n");
  const kind = mode.slice(5);
  if (["dead", "reused", "zombie", "unknown", "proc-unavailable"].includes(kind)) save("proc-mode.json", kind);
  else if (kind === "oldboot") save("boot.json", "22222222-2222-4222-8222-222222222222");
  else if (kind === "missing") unlinkSync(leaseFile);
  else if (kind === "wrong-token") writeFileSync(leaseFile, JSON.stringify({ ...lease, token: "foreign-token" }));
  else if (kind === "legacy-lease") writeFileSync(leaseFile, JSON.stringify({ ...lease, version: 0 }));
  else if (kind === "corrupt-lease") writeFileSync(leaseFile, "not json");
  else if (kind === "corrupt-proc") save("proc-mode.json", "corrupt");
  else if (kind === "foreign-machine") writeFileSync(leaseFile, JSON.stringify({ ...lease, machineId: "b".repeat(32) }));
  else if (kind === "foreign-namespace") writeFileSync(leaseFile, JSON.stringify({ ...lease, pidNamespace: "pid:[456]" }));
  else assert.equal(kind, "live");
  const rt = await runtime("cold-reader");
  const response = await rt.tool("subagent_message", { name: "Recall", message: "restricted cold followup" });
  assert.equal(calls("inspect").length, 0, "foreign-server panes are not inspected");
  assert.equal(calls("close").length, 0, "foreign-server panes are not closed");
  assert.equal(calls("steer").length, 0, "foreign-server panes are not steered");
  if (["dead", "reused", "zombie", "oldboot"].includes(kind)) {
    assert.equal(response.details.status, "started", "proven-dead writer is resumable after mux cold restart");
    assert.equal(response.details.sessionFile, original.sessionFile);
    assert.equal(response.details.name, original.name);
    assert.equal(calls("spawn").length, 2);
    assert.equal(calls("dispatch").length, 2);
    assert.match(calls("dispatch").at(-1).args[1], /--no-extensions/);
    assert.match(calls("dispatch").at(-1).args[1], /--tools 'read,bash,ask_question'/);
    assert.deepEqual(owner(original).loadout, old.loadout);
    assert.equal(owner(original).policy.entryCountBefore, 2);
    assert.equal(existsSync(`${original.sessionFile}.exit`), false);
    assert.equal(existsSync(`${original.sessionFile}.ask`), false);
    finishSurface(response.details, "COLD_FOLLOWUP_RESULT");
    await waitFor(() => rt.messages.length === 1);
    assert.match(rt.messages[0].content, /COLD_FOLLOWUP_RESULT/);
    assert.doesNotMatch(rt.messages[0].content, /OLD_COLD_OUTPUT|STALE_ERROR/);
    assert.equal(calls("close").length, 1);
    assert.notEqual(calls("close")[0].args[0], old.surface);
  } else {
    assert.ok(response.details.error, "live or unknown writer stays fail-closed");
    assert.equal(calls("spawn").length, 1);
    assert.equal(calls("dispatch").length, 1);
    assert.equal(owner(original).token, old.token);
    assert.equal(rt.messages.length, 0);
  }
  rt.stop();
} else if (mode === "registry-failure") {
  mkdirSync(file("artifacts/parent-session/subagent-registry.json"), { recursive: true });
  const rt = await runtime("registry-failure");
  await assert.rejects(() => rt.tool("subagent", { agent: "recall-fixture", name: "Recall", task: "must not dispatch" }));
  assert.equal(calls("spawn").length, 1);
  assert.equal(calls("dispatch").length, 0, "failed durable registration prevents dispatch");
  assert.equal(calls("close").length, 1);
  rt.stop();
} else if (mode === "terminal-at-recall") {
  save("late.json", true);
  const old = await runtime("old-terminal");
  const run = await launch(old);
  old.stop();
  finishSurface(run, "TERMINAL_BEFORE_RECALL");
  const rt = await runtime("terminal-recalled");
  assert.equal(rt.messages.length, 1, "startup settles the completed writer exactly once");
  assert.equal(rt.module.__test__.runningSubagents.size, 0);
  const followup = await rt.tool("subagent_message", { name: "Recall", message: "never type this into the completed shell" });
  assert.equal(followup.details.status, "started");
  assert.equal(calls("spawn").length, 2);
  assert.equal(calls("steer").length, 0, "completed shells are never steered");
  finishSurface(followup.details, "NEW_TERMINAL_FOLLOWUP");
  await waitFor(() => rt.messages.length === 2);
  assert.equal(old.messages.length, 0);
  rt.stop();
} else if (mode === "reload" || mode === "late-watcher") {
  if (mode === "late-watcher") save("late.json", true);
  const old = await runtime("old-runtime");
  const run = await launch(old);
  old.stop();
  const recalled = await runtime("reloaded-runtime");
  await delay(75);
  await verifyRecall(recalled, run);
  assert.equal(old.messages.length, 0);
  await verifyCompletionAndFollowup(recalled, run);
  assert.equal(old.messages.length, 0);
} else if (["legacy-completed", "legacy-pending", "modern-completed-missing"].includes(mode)) {
  const old = await runtime("pre-v2-parent");
  const run = await launch(old);
  old.stop();
  const metadata = owner(run);
  unlinkSync(`${run.sessionFile}.owner.json`);
  unlinkSync(`${run.sessionFile}.writer.json`);
  if (mode !== "modern-completed-missing") unlinkSync(`${run.sessionFile}.owner-v2`);
  save(`surface-${metadata.surface}.json`, {closed:true});
  mkdirSync(join(run.launchScriptFile, ".."), {recursive:true});
  writeFileSync(run.launchScriptFile, `# Session: ${run.sessionFile}\n# Pre-v2 fixture has no writer token.\n`);
  const branch = [
    {type:"message", message:{role:"toolResult", toolName:"subagent", details:run}},
    {type:"custom_message", customType:"subagent_result", details:{name:run.name, sessionFile:run.sessionFile, exitCode:0}},
  ];
  if (mode === "legacy-pending") branch.push({type:"message", message:{role:"toolResult", toolName:"subagent_message", details:{...run, status:"started"}}});
  ctx.sessionManager.getBranch = () => branch;
  const rt = await runtime("legacy-followup");
  const response = await rt.tool("subagent_message", {name:run.name, message:"legacy followup"});
  if (mode === "legacy-completed") {
    assert.equal(response.details.status, "started", "known completed pre-v2 handles remain resumable");
    assert.equal(response.details.sessionFile, run.sessionFile);
    assert.equal(calls("spawn").length, 2);
  } else {
    assert.ok(response.details.error, "pending launch or missing modern ownership stays fail-closed");
    assert.equal(calls("spawn").length, 1);
  }
  rt.stop();
} else if (mode === "prepare-replacement") {
  const { ManagedRuns } = await import(new URL("managed-run.ts", source));
  const { createStatusState } = await import(new URL("status.ts", source));
  const manager = new ManagedRuns({moduleSignal: () => new AbortController().signal,
    shellReadyDelayMs: () => 0, refresh() {}, tick() {}, present: r => r.summary, sendMessage() {}});
  const startTime = Date.now();
  await assert.rejects(manager.launch({id:"preparing", name:"Recall", task:"offline", startTime,
    sessionFile:file("preparing.jsonl"), parentArtifactDir:file("artifacts/parent-session"),
    activityFile:file("preparing.activity.json"), interactive:false,
    statusState:createStatusState({source:"pi", startTimeMs:startTime})}, {kind:"initial"}, () => {
      save("incarnation.json", {dev:"1", ino:"99", ctimeNs:"100"});
      throw new Error("preparation failed after replacement");
    }), /preparation failed/);
  assert.equal(calls("close").length, 0, "failed preparation cannot close replacement-server panes");
  manager.dispose();
} else if (mode === "completion-during-recall") {
  const rt = await runtime("concurrent-completion");
  const run = await launch(rt);
  save("async-read-delay.json", 75);
  const followup = rt.tool("subagent_message", {name:run.name, message:"followup at completion boundary"});
  await delay(10);
  finishSurface(run, "CONCURRENT_ORIGINAL_RESULT");
  save("proc-mode.json", "dead");
  const response = await followup;
  assert.equal(response.details.status, "started");
  assert.equal(rt.messages.length, 1, "lock contention cannot discard the original completion");
  assert.match(rt.messages[0].content, /CONCURRENT_ORIGINAL_RESULT/);
  assert.equal(calls("steer").length, 0, "a completed writer is not steered into its shell");
  assert.equal(calls("spawn").length, 2);
  finishSurface(response.details, "CONCURRENT_FOLLOWUP_RESULT");
  await waitFor(() => rt.messages.length === 2);
  assert.doesNotMatch(rt.messages[1].content, /CONCURRENT_ORIGINAL_RESULT/);
  rt.stop();
} else if (mode === "dead-missing-surface") {
  const old = await runtime("dead-original");
  const run = await launch(old);
  old.stop();
  save("proc-mode.json", "dead");
  save(`surface-${owner(run).surface}.json`, {closed:true});
  const rt = await runtime("dead-recalled");
  const followup = await rt.tool("subagent_message", {name:"Recall", message:"safe dead-writer followup"});
  assert.equal(followup.details.status, "started");
  assert.equal(followup.details.sessionFile, run.sessionFile);
  assert.equal(followup.details.name, run.name);
  assert.equal(calls("spawn").length, 2);
  assert.equal(calls("steer").length, 0, "missing owned shell is never steered");
  rt.stop();
} else if (mode === "fenced-live-runtime" || mode === "delivery-throws") {
  // Even if a predecessor's disposal signal is lost, its lease cannot close
  // or deliver after another supervisor takes over the same writer.
  const { ManagedRuns } = await import(new URL("managed-run.ts", source));
  const { createStatusState } = await import(new URL("status.ts", source));
  const messages = [[], []];
  const make = (n) => new ManagedRuns({ moduleSignal: () => new AbortController().signal, shellReadyDelayMs: () => 0, refresh() {}, tick() {}, present: (r) => r.summary, sendMessage: (m) => { messages[n].push(m); if (mode === "delivery-throws") throw new Error("already enqueued"); } });
  const first = make(0), second = make(1);
  const loadout = { agent: "worker", toolAllowlist: "read", model: "offline-default", thinking: null, systemPromptMode: null, identity: null, spawnable: null, autoExit: true, cwd: root, agentDir: file("agent") };
  const parentArtifactDir = file("artifacts/parent-session");
  mkdirSync(parentArtifactDir, { recursive: true });
  const sessionFile = file("fenced.jsonl");
  const startTime = Date.now();
  const run = await first.launch({ id: "same-id", name: "Recall", task: "original task", sessionFile, parentArtifactDir, startTime, activityFile: file("same-id.json"), interactive: false, statusState: createStatusState({ source: "pi", startTimeMs: startTime }) }, { kind: "initial" }, () => ({ kind: "pi", parts: ["pi", "--session", `'${sessionFile}'`], loadout, autoExit: true, launchScriptFile: file("fake-script"), scriptPreamble: "offline" }), (r) => save("artifacts/parent-session/subagent-registry.json", { Recall: { sessionFile: r.sessionFile, sessionId: null } }));
  const adopted = await second.recall(parentArtifactDir, "Recall", sessionFile);
  assert.equal(adopted.id, run.id);
  finishSurface(run, "FENCED_RESULT");
  await waitFor(() => messages[1].length === 1);
  await delay(75);
  assert.equal(messages[0].length, 0);
  assert.equal(calls("close").length, 1);
  assert.equal(await second.recall(parentArtifactDir, "Recall", sessionFile), undefined);
  assert.equal(messages[1].length, 1, "a throwing delivery seam is never retried");
  first.dispose(); second.dispose();
} else {
  const rt = await runtime("original");
  const run = await launch(rt);
  rt.stop();
  const value = owner(run);
  if (mode === "foreign-mux") value.mux += "-foreign";
  else if (mode === "foreign-parent") value.run.parentArtifactDir = file("foreign-parent");
  else if (mode === "foreign-name") value.run.name = "Other";
  else if (mode === "legacy") value.version = 1;
  else if (mode === "missing-owner") unlinkSync(`${run.sessionFile}.owner.json`);
  else if (mode === "corrupt") delete value.policy;
  else if (mode === "corrupt-loadout") value.loadout = {};
  else if (mode === "unknown-mux") save("identity.json", "");
  else if (mode === "reused-incarnation") save("incarnation.json", { dev: "1", ino: "99", ctimeNs: "100" });
  else if (mode === "unknown-surface") save(`surface-${value.surface}.json`, { unknown: true });
  else if (mode === "incomplete-dispatch") value.phase = "prepared";
  else if (mode === "busy-lock") mkdirSync(`${run.sessionFile}.owner.lock`);
  else if (mode === "misleading-monitor-error") {
    value.delivered = true;
    save("proc-mode.json", "dead");
    save(`surface-${value.surface}.json`, { unavailable: true });
  }
  else if (["live-lost-pane", "unknown-lost-pane", "live-stale-sentinel"].includes(mode)) {
    value.delivered = true; // Prior watcher noticed completion, but could not kill the writer.
    save(`surface-${value.surface}.json`, mode === "live-stale-sentinel" ? { done: true, closed: false } : { closed: true });
    if (mode === "unknown-lost-pane") unlinkSync(`${run.sessionFile}.writer.json`);
  }
  else assert.fail(`Unknown mode: ${mode}`);
  if (mode !== "missing-owner") setOwner(run, value);
  const recalled = await runtime("refused");
  const response = await recalled.tool("subagent_message", { name: "Recall", message: "must not dispatch" });
  assert.ok(response.details.error, "unknown/foreign metadata rejected");
  assert.equal(calls("spawn").length, 1);
  assert.equal(calls("dispatch").length, 1);
  assert.equal(calls("steer").length, 0);
  assert.equal(calls("close").length, 0);
  assert.equal(recalled.messages.length, 0);
  recalled.stop();
}
console.log(`PASS ${process.env.PI_RECALL_BACKEND} ${mode}`);
