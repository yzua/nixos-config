// File-backed fake surfaces survive harness process restart. Never executes CLI.
import assert from "node:assert/strict";
import { appendFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import reporter from "../../home-manager/modules/ai/pi/extensions/interactive-subagents/pi-extension/subagents/subagent-done.ts";
const path = (name) => join(process.env.PI_RECALL_ROOT, name);
const read = (name, fallback) => existsSync(path(name)) ? JSON.parse(readFileSync(path(name), "utf8")) : fallback;
export function record(op, ...args) {
  appendFileSync(path("calls.jsonl"), JSON.stringify({ op, args }) + "\n");
}
export function isHerdrSurface(surface) { return /^w[0-9A-HJKMNP-TV-Z]+:p[0-9A-HJKMNP-TV-Z]+$/.test(surface); }
export function isSurfaceId(surface) { return process.env.PI_RECALL_BACKEND === "herdr" ? isHerdrSurface(surface) : /^%\d+$/.test(surface); }
export function muxIdentity() {
  const incarnation = read("incarnation.json", { dev: "1", ino: "2", ctimeNs: "3" });
  return read("identity.json", process.env.PI_RECALL_BACKEND === "herdr" ? `herdr:/offline/socket:${incarnation.dev}:${incarnation.ino}:${incarnation.ctimeNs}` : "/offline/tmux,123");
}
export function isMuxAvailable() { return true; }
export function muxSetupHint() { return "offline only"; }
export function shellEscape(s) { return "'" + s.replace(/'/g, "'\\''") + "'"; }
export function createSurface(name) {
  writeFileSync(path("proc-mode.json"), JSON.stringify("live"));
  const n = read("count.json", 0) + 1;
  writeFileSync(path("count.json"), JSON.stringify(n));
  const surface = process.env.PI_RECALL_BACKEND === "herdr" ? `w1:p${n}` : `%${n}`;
  writeFileSync(path(`surface-${surface}.json`), JSON.stringify({ done: false, closed: false }));
  record("spawn", surface, name);
  return surface;
}
export function sendLongCommand(surface, command) {
  const sessionFile = command.match(/--session '([^']+)'/)[1];
  const owner = JSON.parse(readFileSync(`${sessionFile}.owner.json`, "utf8"));
  assert.equal(owner.surface, surface);
  assert.equal(owner.version, 2);
  assert.equal(owner.phase, "prepared", "dispatch uncertainty is persisted before sending");
  assert.equal(owner.run.name, "Recall");
  assert.equal(owner.run.activityFile.endsWith(`${owner.run.id}.json`), true);
  assert.equal(owner.policy.kind === "initial" || owner.policy.kind === "resume", true);
  assert.equal(owner.loadout.toolAllowlist.includes("read"), true);
  assert.equal(owner.loadout.model, "offline-default");
  const registry = JSON.parse(readFileSync(join(owner.run.parentArtifactDir, "subagent-registry.json"), "utf8"));
  assert.equal(registry.Recall.sessionFile, sessionFile, "registry persisted before dispatch");
  if (!existsSync(sessionFile)) writeFileSync(sessionFile, JSON.stringify({ type: "session", id: "original-child-session", version: 3 }) + "\n");
  assert.ok(command.includes(`PI_SUBAGENT_WRITER_TOKEN='${owner.token}'`));
  // Invoke the actual reporter's startup hook, but never run a model or CLI.
  const keys = ["PI_SUBAGENT_SESSION", "PI_SUBAGENT_ID", "PI_SUBAGENT_WRITER_TOKEN", "PI_SUBAGENT_ACTIVITY_FILE"];
  const previous = Object.fromEntries(keys.map((key) => [key, process.env[key]]));
  Object.assign(process.env, { PI_SUBAGENT_SESSION: sessionFile, PI_SUBAGENT_ID: owner.run.id, PI_SUBAGENT_WRITER_TOKEN: owner.token, PI_SUBAGENT_ACTIVITY_FILE: owner.run.activityFile });
  try {
    const events = new Map();
    reporter({ on: (name, handler) => events.set(name, handler), getAllTools: () => [], registerShortcut() {}, registerTool() {} });
    events.get("session_start")({}, { ui: { setWidget() {} } });
    const lease = JSON.parse(readFileSync(`${sessionFile}.writer.json`, "utf8"));
    assert.equal(lease.token, owner.token);
    assert.equal(lease.runningChildId, owner.run.id);
    assert.equal(lease.pid, process.pid);
    assert.equal(lease.startTime, "101");
  } finally {
    for (const key of keys) { if (previous[key] === undefined) delete process.env[key]; else process.env[key] = previous[key]; }
  }
  record("dispatch", surface, command);
}
export function sendCommand(surface, command) { readScreen(surface); record("steer", surface, command); }
export async function readScreenAsync(surface) { return readScreen(surface); }
export function readScreen(surface) {
  record("inspect", surface);
  const state = read(`surface-${surface}.json`, null);
  if (!state || state.closed || state.unknown) throw new Error("Cannot inspect fake surface");
  return state.done ? "__SUBAGENT_DONE_0__" : "offline child running";
}
export function closeSurface(surface) {
  const state = read(`surface-${surface}.json`, {});
  writeFileSync(path(`surface-${surface}.json`), JSON.stringify({ ...state, closed: true }));
  writeFileSync(path("proc-mode.json"), JSON.stringify("dead"));
  record("close", surface);
}
export async function pollForExit(surface, signal, options) {
  // Optional late read simulates a terminal capture resolving after disposal.
  const late = read("late.json", false);
  if (late) await new Promise((r) => setTimeout(r, 50));
  for (;;) {
    if (!late && signal.aborted) throw new Error("Aborted fake watcher");
    const state = read(`surface-${surface}.json`, null);
    if (!state || state.closed) return { reason: "error", exitCode: 1, errorMessage: `Subagent pane ${surface} disappeared before reporting completion.` };
    if (state.done) return { reason: "sentinel", exitCode: 0 };
    options.onTick?.(0);
    await new Promise((r) => setTimeout(r, 5));
    if (signal.aborted) throw new Error("Aborted fake watcher");
  }
}
