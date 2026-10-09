import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, rmSync, existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { test } from "node:test";
import { pollForExit } from "../pi-extension/subagents/run-evidence.ts";

function fixture(t: { after(fn: () => void): void }): string {
  const dir = mkdtempSync(join(tmpdir(), "pi-run-evidence-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return join(dir, "child.jsonl");
}

for (const payload of [{ type: "ping" }, { type: "done" }, {}, null]) {
  test(`consumes ${JSON.stringify(payload)} sidecars as done evidence, not terminal exit`, async (t) => {
    const sessionFile = fixture(t);
    writeFileSync(`${sessionFile}.exit`, JSON.stringify(payload));
    assert.deepEqual(
      await pollForExit("%1", new AbortController().signal, { interval: 1, sessionFile }),
      { reason: "done", evidence: "sidecar", exitCode: 0 },
    );
    assert.ok(!existsSync(`${sessionFile}.exit`));
  });
}
for (const errorMessage of ["Provider overload", undefined, " "]) {
  test(`consumes error sidecars with ${JSON.stringify(errorMessage)} message`, async (t) => {
    const sessionFile = fixture(t);
    writeFileSync(`${sessionFile}.exit`, JSON.stringify({ type: "error", errorMessage }));
    const exit = await pollForExit("%1", new AbortController().signal, {
      interval: 1,
      sessionFile,
    });
    assert.equal(exit.evidence, "sidecar");
    assert.equal(exit.reason, "error");
    assert.equal(exit.exitCode, 1);
    if (errorMessage?.trim()) assert.equal(exit.errorMessage, errorMessage);
    else assert.match(exit.errorMessage!, /no errorMessage/);
    assert.ok(!existsSync(`${sessionFile}.exit`));
  });
}

test("Claude Stop file is retained and distinguished from shell exit evidence", async (t) => {
  const sentinelFile = fixture(t);
  writeFileSync(sentinelFile, "CLAUDE_RESULT");
  assert.deepEqual(
    await pollForExit("%1", new AbortController().signal, { interval: 1, sentinelFile }),
    { reason: "sentinel", evidence: "sentinel-file", exitCode: 0 },
  );
  assert.ok(existsSync(sentinelFile));
});

test("disposal wins over already-published completion without consuming it", async (t) => {
  const sessionFile = fixture(t);
  writeFileSync(`${sessionFile}.exit`, JSON.stringify({ type: "done" }));
  await assert.rejects(
    pollForExit("%1", AbortSignal.abort(), { interval: 1, sessionFile }),
    /Aborted/,
  );
  assert.ok(existsSync(`${sessionFile}.exit`));
});
