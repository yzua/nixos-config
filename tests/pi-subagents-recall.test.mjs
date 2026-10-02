// Run: node --test tests/pi-subagents-recall.test.mjs (Node >= 24).
// Fresh Node subprocesses use a closed offline loader; no Pi/model/mux CLI runs.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
const fixture = (name) => fileURLToPath(new URL(`pi-subagents-recall/${name}`, import.meta.url));
const scenarios = ["reload", "terminal-at-recall", "registry-failure", "late-watcher", "fenced-live-runtime", "delivery-throws", "restart", "reused-incarnation", "foreign-mux", "foreign-parent", "foreign-name", "legacy", "missing-owner", "corrupt", "corrupt-loadout", "unknown-mux", "unknown-surface", "incomplete-dispatch", "busy-lock", "live-lost-pane", "unknown-lost-pane", "live-stale-sentinel", ...["dead", "reused", "zombie", "oldboot", "live", "missing", "wrong-token", "legacy-lease", "corrupt-lease", "corrupt-proc", "foreign-machine", "foreign-namespace", "unknown", "proc-unavailable"].map((name) => `cold-${name}`)];
for (const backend of ["tmux", "herdr"]) {
  for (const scenario of scenarios) {
    test(`${backend}: ${scenario}`, () => {
      const root = mkdtempSync(join(tmpdir(), "pi-recall-offline-"));
      try {
        const env = Object.fromEntries(Object.entries(process.env).filter(([key]) =>
          !key.startsWith("HERDR_") && !key.startsWith("PI_SUBAGENT") && !["TMUX", "TMUX_PANE", "NODE_OPTIONS"].includes(key)));
        Object.assign(env, { HOME: root, PI_CODING_AGENT_DIR: join(root, "agent"), PI_RECALL_ROOT: root, PI_RECALL_BACKEND: backend, PI_SUBAGENT_SHELL_READY_DELAY_MS: "0" });
        const run = (mode) => {
          const stdout = execFileSync(process.execPath, ["--no-warnings", "--experimental-transform-types", "--loader", fixture("loader.mjs"), fixture("scenario.mjs"), mode], { env, cwd: root, encoding: "utf8", timeout: 10000 });
          if (mode !== "restart-writer") assert.match(stdout, /PASS/);
        };
        if (scenario === "restart") { run("restart-writer"); run("restart-reader"); }
        else if (scenario.startsWith("cold-")) { run("restart-writer"); run(scenario); }
        else run(scenario);
      } finally { rmSync(root, { recursive: true, force: true }); }
    });
  }
}
