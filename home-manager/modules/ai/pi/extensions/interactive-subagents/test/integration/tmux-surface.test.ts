/**
 * Integration tests for the tmux surface layer.
 *
 * These tests exercise real tmux operations: creating panes,
 * sending commands, reading screen output, and closing panes.
 * No LLM calls — fast and free.
 *
 * Run inside tmux:
 *   tmux new 'npm run test:integration'
 */
import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import { unlinkSync } from "node:fs";
import {
  getAvailableBackends,
  createTestEnv,
  cleanupTestEnv,
  createTrackedSurface,
  createTrackedSurfaceSplit,
  focusSurface,
  getFocusedSurface,
  waitForFocusedSurface,
  untrackSurface,
  sendCommand,
  sendLongCommand,
  readScreen,
  readScreenAsync,
  closeSurface,
  sleep,
  uniqueId,
  trackTempFile,
  waitForFile,
  waitForScreen,
  type TestEnv,
} from "./harness.ts";

const backends = getAvailableBackends();
const FOCUS_TEST_SHELL_READY_DELAY_MS = Number(process.env.PI_SUBAGENT_SHELL_READY_DELAY_MS ?? "2500");

if (backends.length === 0) {
  console.log("⚠️  tmux is not available — skipping tmux-surface integration tests");
  console.log("   Run inside tmux to enable these tests.");
}

for (const backend of backends) {
  describe(`tmux-surface [${backend}]`, { timeout: 60_000 }, () => {
    let env: TestEnv;

    before(() => {
      env = createTestEnv();
    });

    after(() => {
      cleanupTestEnv(env);
    });

    it("keeps focus on the active surface while creating and targeting subagent surfaces", async () => {
      const anchor = createTrackedSurfaceSplit(env, "focus-anchor", "right");
      await sleep(1000);

      focusSurface(anchor);
      await waitForFocusedSurface(anchor, 10_000);

      const childA = createTrackedSurface(env, "focus-child-a");
      await sleep(FOCUS_TEST_SHELL_READY_DELAY_MS);
      assert.equal(getFocusedSurface(), anchor);

      const childB = createTrackedSurface(env, "focus-child-b");
      await sleep(FOCUS_TEST_SHELL_READY_DELAY_MS);
      assert.equal(getFocusedSurface(), anchor);

      const markerA = uniqueId();
      const markerB = uniqueId();
      sendCommand(childA, `echo "FOCUS_A_${markerA}"`);
      sendCommand(childB, `echo "FOCUS_B_${markerB}"`);

      await Promise.all([
        waitForScreen(childA, new RegExp(`FOCUS_A_${markerA}`), 20_000, 50),
        waitForScreen(childB, new RegExp(`FOCUS_B_${markerB}`), 20_000, 50),
      ]);
      assert.equal(getFocusedSurface(), anchor);
    });

    it("creates a surface, sends a command, reads output, and closes it", async () => {
      const surface = createTrackedSurface(env, "echo-test");
      await sleep(1000);

      const marker = uniqueId();
      sendCommand(surface, `echo "MARKER_${marker}"`);
      await sleep(1500);

      const screen = readScreen(surface, 50);
      assert.ok(
        screen.includes(`MARKER_${marker}`),
        `Expected screen to contain MARKER_${marker}. Got:\n${screen}`,
      );

      closeSurface(surface);
      untrackSurface(env, surface);
    });

    it("preserves shell special characters in echo output", async () => {
      const surface = createTrackedSurface(env, "escape-test");
      await sleep(1000);

      const marker = uniqueId();
      // Single-quoted string — $ and " are literal inside single quotes
      sendCommand(surface, `echo 'SPEC_${marker}_$HOME_"quotes"_done'`);
      await sleep(1500);

      const screen = readScreen(surface, 50);
      assert.ok(
        screen.includes(`SPEC_${marker}`),
        `Expected special-char output. Got:\n${screen}`,
      );
      // $ should be literal inside single quotes
      assert.ok(
        screen.includes("$HOME"),
        `Expected literal $HOME in output. Got:\n${screen}`,
      );
    });

    it("sends a long command via script file without truncation", async () => {
      const surface = createTrackedSurface(env, "long-cmd-test");
      await sleep(1000);

      const marker = uniqueId();
      const longValue = "X".repeat(500);
      const command = `echo "LONG_${marker}_${longValue}_END"`;

      sendLongCommand(surface, command);
      await sleep(2000);

      const screen = readScreen(surface, 50);
      assert.ok(
        screen.includes(`LONG_${marker}`),
        `Expected long command output. Got:\n${screen.slice(0, 300)}...`,
      );
      assert.ok(
        screen.includes("_END"),
        `Expected full output (not truncated). Got:\n${screen.slice(-300)}`,
      );
    });

    it("reads screen asynchronously", async () => {
      const surface = createTrackedSurface(env, "async-read-test");
      await sleep(1000);

      const marker = uniqueId();
      sendCommand(surface, `echo "ASYNC_${marker}"`);
      await sleep(1500);

      const screen = await readScreenAsync(surface, 50);
      assert.ok(
        screen.includes(`ASYNC_${marker}`),
        `Async read should find marker. Got:\n${screen}`,
      );
    });

    it("manages multiple surfaces concurrently", async () => {
      const s1 = createTrackedSurface(env, "multi-1");
      const s2 = createTrackedSurface(env, "multi-2");
      await sleep(1500);

      const m1 = uniqueId();
      const m2 = uniqueId();
      sendCommand(s1, `echo "S1_${m1}"`);
      sendCommand(s2, `echo "S2_${m2}"`);
      await sleep(1500);

      const screen1 = readScreen(s1, 50);
      const screen2 = readScreen(s2, 50);

      assert.ok(screen1.includes(`S1_${m1}`), `Surface 1 missing marker. Got:\n${screen1}`);
      assert.ok(screen2.includes(`S2_${m2}`), `Surface 2 missing marker. Got:\n${screen2}`);
    });

    it("writes output to a file and verifies via surface", async () => {
      const surface = createTrackedSurface(env, "file-test");
      await sleep(1000);

      const marker = uniqueId();
      const filePath = `/tmp/pi-tmux-test-${marker}.txt`;

      sendCommand(surface, `echo "FILE_${marker}" > ${filePath} && echo "WRITTEN_${marker}"`);

      await waitForScreen(surface, new RegExp(`WRITTEN_${marker}`), 10_000, 50);
      const content = await waitForFile(filePath, 10_000, new RegExp(`FILE_${marker}`));
      assert.ok(content.includes(`FILE_${marker}`), `File content wrong. Got: ${content}`);

      // Clean up
      try {
        unlinkSync(filePath);
      } catch {}
    });
  });
}
