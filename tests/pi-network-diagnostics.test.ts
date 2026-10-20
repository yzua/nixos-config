import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import diagnostics, {
  observeBody,
  safeFailure,
} from "../home-manager/modules/ai/pi-base/extensions/network-diagnostics.ts";

test("failure diagnostics allowlist codes and never retain raw messages", () => {
  const secret = "CANARY_TOKEN\r\nAuthorization: secret";
  assert.deepEqual(safeFailure({ code: secret, cause: { code: secret }, message: secret }), {
    code: null,
    causeCode: null,
    signature: "other",
  });
  assert.deepEqual(
    safeFailure({
      code: "ECONNRESET",
      cause: { code: "UND_ERR_SOCKET" },
      message: `The socket connection was closed unexpectedly ${secret}`,
    }),
    {
      code: "ECONNRESET",
      causeCode: "UND_ERR_SOCKET",
      signature: "socket_closed",
    },
  );
});

test("opt-in wrapper preserves request/response/error identity and logs no HTTP data", async () => {
  const directory = mkdtempSync(join(tmpdir(), "pi-network-test-"));
  const priorState = process.env.XDG_STATE_HOME;
  const priorFetch = globalThis.fetch;
  type Callback = (...args: unknown[]) => unknown;
  const handlers = new Map<string, Callback>();
  const commands = new Map<string, { handler: Callback }>();
  const canary = "PRIVATE_CANARY";
  const response = new Response("response-private", {
    status: 200,
    headers: { "set-cookie": canary },
  });
  const failure = Object.assign(
    new Error(`The socket connection was closed unexpectedly: ${canary}`),
    { code: "ECONNRESET" },
  );
  let reject = false;
  let called: unknown[] | undefined;
  const fakeFetch = Object.assign(
    async (...args: unknown[]) => {
      called = args;
      if (reject) throw failure;
      return response;
    },
    { preconnect: () => undefined },
  ) as unknown as typeof fetch;
  try {
    process.env.XDG_STATE_HOME = directory;
    globalThis.fetch = fakeFetch;
    diagnostics({
      registerCommand: (name: string, value: { handler: Callback }) => commands.set(name, value),
      on: (name: string, handler: Callback) => handlers.set(name, handler),
    } as never);
    assert.equal(globalThis.fetch, fakeFetch, "factory must not install a wrapper");
    const ctx = {
      modelRegistry: {
        getAll: () => [{ baseUrl: "https://api.example.invalid/v1", provider: "test" }],
      },
      ui: { notify: () => undefined },
    };
    await commands.get("net-debug")!.handler("on", ctx);
    assert.equal(globalThis.fetch.preconnect, fakeFetch.preconnect);
    const init = {
      method: "POST",
      headers: { Authorization: canary },
      body: `{"prompt":"${canary}"}`,
    };
    const url = `https://api.example.invalid/v1/${canary}?key=${canary}`;
    assert.equal(await fetch(url, init), response);
    assert.equal(called![0], url);
    assert.equal(called![1], init, "must not inject verbose or change options");
    assert.equal(response.body!.locked, false, "must not read or tee the body");
    reject = true;
    await assert.rejects(fetch(url, init), (error) => error === failure);
    handlers.get("message_end")!({ message: { role: "assistant", errorMessage: failure.message } });
    handlers.get("session_shutdown")!();
    assert.equal(globalThis.fetch, fakeFetch);
    const logDir = join(directory, "pi-network");
    const file = join(logDir, readdirSync(logDir)[0]);
    const log = readFileSync(file, "utf8");
    assert(!log.includes(canary));
    assert(!log.includes("Authorization"));
    assert(!log.includes("set-cookie"));
    assert(!log.includes("api.example.invalid"));
    assert(!log.includes("response-private"));
    const records = log
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    assert.deepEqual(
      records.map((r) => r.phase),
      [
        "enabled",
        "request_start",
        "response_headers",
        "request_start",
        "fetch_error",
        "assistant_error",
      ],
    );
    assert.equal(records.find((r) => r.phase === "fetch_error").code, "ECONNRESET");
    assert.equal(statSync(file).mode & 0o777, 0o600);
    assert.equal(statSync(logDir).mode & 0o777, 0o700);
  } finally {
    handlers.get("session_shutdown")?.();
    globalThis.fetch = priorFetch;
    if (priorState === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = priorState;
    rmSync(directory, { recursive: true, force: true });
  }
});

test("body observer captures the post-header socket cause without reading ahead", async () => {
  const records: Record<string, unknown>[] = [];
  const chunk = new Uint8Array([1, 2, 3]);
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const failure = Object.assign(
    new Error("The socket connection was closed unexpectedly PRIVATE_BODY"),
    { code: "ConnectionClosed" },
  );
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
  });
  const response = new Response(body);
  observeBody(
    response,
    (r) => records.push(r),
    () => 12,
  );
  assert.equal(response.body, body);
  assert.equal(body.locked, false);
  assert.equal(records.length, 0);
  controller.enqueue(chunk);
  const reader = body.getReader();
  assert.equal((await reader.read()).value, chunk);
  controller.error(failure);
  await assert.rejects(reader.read(), (error) => error === failure);
  reader.releaseLock();
  assert.equal(body.locked, false);
  assert.deepEqual(
    records.map((r) => r.phase),
    ["body_first_chunk", "body_error"],
  );
  assert.equal(records[1].code, "ConnectionClosed");
  assert.equal(records[1].chunks, 1);
  assert.equal(records[1].bodyBytes, 3);
  assert(!JSON.stringify(records).includes("PRIVATE_BODY"));
});

test("native async iterator EOF and cancellation retain data and cancel reason", async () => {
  for (const factory of [
    (b: ReadableStream<Uint8Array>) => b.values(),
    (b: ReadableStream<Uint8Array>) => b[Symbol.asyncIterator](),
  ]) {
    const records: Record<string, unknown>[] = [];
    const chunk = new Uint8Array([4, 5]);
    let baselineReason: unknown;
    const baseline = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(chunk);
      },
      cancel(reason) {
        baselineReason = reason;
      },
    });
    const baselineIterator = factory(baseline);
    await baselineIterator.next();
    await baselineIterator.return!("PRIVATE_CANCEL" as never);
    let cancelReason: unknown;
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(chunk);
      },
      cancel(reason) {
        cancelReason = reason;
      },
    });
    observeBody(
      new Response(body),
      (r) => records.push(r),
      () => 25,
    );
    const iterator = factory(body);
    assert.equal((await iterator.next()).value, chunk);
    await iterator.return!("PRIVATE_CANCEL" as never);
    assert.equal(cancelReason, baselineReason);
    assert.equal(records.at(-1)!.phase, "body_cancelled");
    assert(!JSON.stringify(records).includes("PRIVATE_CANCEL"));
  }
  const records: Record<string, unknown>[] = [];
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      c.enqueue(new Uint8Array([6]));
      c.close();
    },
  });
  observeBody(
    new Response(body),
    (r) => records.push(r),
    () => 30,
  );
  for await (const chunk of body) assert.equal(chunk[0], 6);
  assert.equal(records.at(-1)!.phase, "body_end");
  assert.equal(records.at(-1)!.bodyBytes, 1);
});

test("observer reporting failures cannot break a successful consumer", async () => {
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      c.enqueue(new Uint8Array([7]));
      c.close();
    },
  });
  observeBody(
    new Response(body),
    () => {
      throw new Error("observer unavailable");
    },
    () => 1,
  );
  const reader = body.getReader();
  assert.equal((await reader.read()).value![0], 7);
  assert.equal((await reader.read()).done, true);
  reader.releaseLock();
});

test("stopped diagnostic window cannot write into a later window", async () => {
  const directory = mkdtempSync(join(tmpdir(), "pi-network-generation-"));
  const priorState = process.env.XDG_STATE_HOME;
  const priorFetch = globalThis.fetch;
  type Callback = (...args: unknown[]) => unknown;
  const handlers = new Map<string, Callback>();
  const commands = new Map<string, { handler: Callback }>();
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
  });
  try {
    process.env.XDG_STATE_HOME = directory;
    globalThis.fetch = (async () => new Response(body)) as typeof fetch;
    diagnostics({
      registerCommand: (name: string, value: { handler: Callback }) => commands.set(name, value),
      on: (name: string, handler: Callback) => handlers.set(name, handler),
    } as never);
    const ctx = {
      modelRegistry: {
        getAll: () => [{ baseUrl: "https://api.example.invalid/v1", provider: "test" }],
      },
      ui: { notify: () => undefined },
    };
    await commands.get("net-debug")!.handler("on", ctx);
    const response = await fetch("https://api.example.invalid/v1");
    const reader = response.body!.getReader();
    await commands.get("net-debug")!.handler("off", ctx);
    await commands.get("net-debug")!.handler("on", ctx);
    controller.error(new Error("The socket connection was closed unexpectedly"));
    await assert.rejects(reader.read());
    handlers.get("session_before_compact")!({ reason: "manual" });
    handlers.get("session_compact_failed")!({
      reason: "manual",
      aborted: false,
      errorMessage:
        "Summarization failed: The socket connection was closed unexpectedly PRIVATE_SUMMARY",
    });
    await commands.get("net-debug")!.handler("off", ctx);
    const files = readdirSync(join(directory, "pi-network")).sort();
    assert.equal(files.length, 2);
    const current = files
      .map((f) => readFileSync(join(directory, "pi-network", f), "utf8"))
      .find((s) => s.includes("compaction_start"))!;
    const records = current
      .trim()
      .split("\n")
      .map((l) => JSON.parse(l));
    assert.deepEqual(
      records.map((r) => r.phase),
      ["enabled", "compaction_start", "compaction_end"],
    );
    assert.equal(records[2].signature, "socket_closed");
    assert(!current.includes("PRIVATE_SUMMARY"));
  } finally {
    handlers.get("session_shutdown")?.();
    globalThis.fetch = priorFetch;
    if (priorState === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = priorState;
    rmSync(directory, { recursive: true, force: true });
  }
});
