import { createHash } from "node:crypto";
import { appendFileSync, chmodSync, closeSync, constants, mkdirSync, openSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const CODES = new Set([
  "ECONNRESET",
  "ECONNREFUSED",
  "ETIMEDOUT",
  "ENOTFOUND",
  "EAI_AGAIN",
  "EPIPE",
  "ERR_SOCKET_CLOSED",
  "ConnectionClosed",
  "ConnectionRefused",
  "ConnectionReset",
  "ABORT_ERR",
  "UND_ERR_SOCKET",
  "UND_ERR_CONNECT_TIMEOUT",
  "UND_ERR_HEADERS_TIMEOUT",
  "UND_ERR_BODY_TIMEOUT",
]);

export function safeFailure(error: unknown) {
  const e = error as { code?: unknown; message?: unknown; cause?: { code?: unknown } };
  const message = typeof e?.message === "string" ? e.message.toLowerCase() : "";
  return {
    code: typeof e?.code === "string" && CODES.has(e.code) ? e.code : null,
    causeCode: typeof e?.cause?.code === "string" && CODES.has(e.cause.code) ? e.cause.code : null,
    signature: message.includes("socket connection was closed unexpectedly")
      ? "socket_closed"
      : message.includes("connection error")
        ? "connection_error"
        : message.includes("aborted")
          ? "aborted"
          : "other",
  };
}

// Observe the existing consumer only: no clone/tee, extra read, new stream or
// replacement Response. Reader/iterator results, promises and errors stay intact.
export function observeBody(
  response: Response,
  report: (data: Record<string, unknown>) => void,
  elapsed: () => number,
  signal?: AbortSignal | null,
) {
  const body = response.body;
  if (!body) return;
  let chunks = 0;
  let bodyBytes = 0;
  let lastDataMs = elapsed();
  let terminal = false;
  const seen = new WeakSet<object>();
  const emit = (data: Record<string, unknown>) => {
    try {
      report(data);
    } catch {
      /* Never fail the consumer. */
    }
  };
  const end = (phase: string, error?: unknown) => {
    if (terminal) return;
    terminal = true;
    const elapsedMs = elapsed();
    emit({
      phase,
      elapsedMs,
      idleMs: elapsedMs - lastDataMs,
      chunks,
      bodyBytes,
      signalAborted: signal?.aborted ?? false,
      ...(phase === "body_error" ? safeFailure(error) : {}),
    });
  };
  const result = (value: IteratorResult<unknown>) => {
    if (terminal) return;
    if (value.done) {
      end("body_end");
      return;
    }
    chunks++;
    if (ArrayBuffer.isView(value.value) || value.value instanceof ArrayBuffer) {
      bodyBytes += value.value.byteLength;
    }
    lastDataMs = elapsed();
    if (chunks === 1) emit({ phase: "body_first_chunk", elapsedMs: lastDataMs });
  };
  const observe = (consumer: object, key: "read" | "next" | "cancel" | "return") => {
    const target = consumer as Record<string, unknown>;
    const original = target[key];
    if (typeof original !== "function") return;
    Object.defineProperty(target, key, {
      configurable: true,
      writable: true,
      value: function (this: object, ...args: unknown[]) {
        try {
          const promise = Reflect.apply(original, this, args) as Promise<IteratorResult<unknown>>;
          if (key === "read" || key === "next") {
            // Observe a side branch but return the original promise. Observer
            // callbacks never throw, so the discarded branch cannot reject.
            promise.then(
              (value) => {
                try {
                  result(value);
                } catch {
                  /* No effect. */
                }
              },
              (error) => end("body_error", error),
            );
          } else {
            end("body_cancelled");
          }
          return promise;
        } catch (error) {
          end("body_error", error);
          throw error;
        }
      },
    });
  };
  try {
    for (const key of ["getReader", "values", Symbol.asyncIterator] as const) {
      const target = body as unknown as Record<PropertyKey, unknown>;
      const original = target[key];
      if (typeof original !== "function") continue;
      Object.defineProperty(target, key, {
        configurable: true,
        writable: true,
        value: function (this: object, ...args: unknown[]) {
          const consumer = Reflect.apply(original, this, args) as object;
          if (!seen.has(consumer)) {
            seen.add(consumer);
            try {
              for (const method of ["read", "next", "cancel", "return"] as const)
                observe(consumer, method);
            } catch {
              emit({ phase: "body_observer_unavailable" });
            }
          }
          return consumer;
        },
      });
    }
  } catch {
    emit({ phase: "body_observer_unavailable" });
  }
}

// Intentionally NOT Bun verbose:true: that prints credential-bearing headers.
// Keep responses/errors unchanged and never consume/tee the streaming body.
export default function networkDiagnostics(pi: ExtensionAPI) {
  let restore: (() => void) | undefined;
  let fd: number | undefined;
  let bytes = 0;
  let sequence = 0;
  let generation = 0;
  let logPath: string | undefined;
  const write = (data: Record<string, unknown>) => {
    if (fd === undefined) return;
    const line = `${JSON.stringify({ at: new Date().toISOString(), ...data })}\n`;
    const size = Buffer.byteLength(line);
    if (bytes + size > 1024 * 1024) return;
    try {
      appendFileSync(fd, line);
      bytes += size;
    } catch {
      /* Diagnostics must not fail requests. */
    }
  };
  const stop = () => {
    generation++;
    restore?.();
    restore = undefined;
    if (fd !== undefined) {
      try {
        closeSync(fd);
      } catch {
        /* Already closed. */
      }
      fd = undefined;
    }
  };
  pi.registerCommand("net-debug", {
    description: "Toggle private, payload-free model transport diagnostics: /net-debug on|off",
    handler: async (args, ctx) => {
      const action = args.trim();
      if (action === "off") {
        stop();
        ctx.ui.notify("Network diagnostics disabled.", "info");
        return;
      }
      if (action !== "on") {
        ctx.ui.notify(
          restore
            ? `Network diagnostics enabled: ${logPath}`
            : "Use /net-debug on or /net-debug off.",
          "info",
        );
        return;
      }
      if (restore) {
        ctx.ui.notify(`Network diagnostics already enabled: ${logPath}`, "info");
        return;
      }
      const hosts = new Map<string, string>();
      for (const model of ctx.modelRegistry.getAll()) {
        try {
          hosts.set(new URL(model.baseUrl).hostname, model.provider);
        } catch {
          /* Ignore non-HTTP model endpoints. */
        }
      }
      const directory = join(
        process.env.XDG_STATE_HOME || join(homedir(), ".local", "state"),
        "pi-network",
      );
      mkdirSync(directory, { recursive: true, mode: 0o700 });
      chmodSync(directory, 0o700);
      const window = ++generation;
      const record = (data: Record<string, unknown>) => {
        if (generation === window) write(data);
      };
      logPath = join(directory, `${process.pid}-${Date.now()}-${window}.jsonl`);
      fd = openSync(
        logPath,
        constants.O_WRONLY |
          constants.O_APPEND |
          constants.O_CREAT |
          constants.O_EXCL |
          constants.O_NOFOLLOW,
        0o600,
      );
      bytes = 0;
      const original = globalThis.fetch;
      const wrapped = new Proxy(original, {
        apply(target, thisArg, values: [RequestInfo | URL, RequestInit?]) {
          const [input, init] = values;
          let host: string;
          try {
            host = new URL(input instanceof Request ? input.url : String(input)).hostname;
          } catch {
            return Reflect.apply(target, thisArg, values);
          }
          if (!hosts.has(host)) return Reflect.apply(target, thisArg, values);
          const request = ++sequence;
          const started = performance.now();
          const requestBytes = typeof init?.body === "string" ? Buffer.byteLength(init.body) : null;
          const provider = hosts.get(host);
          record({ phase: "request_start", request, requestBytes, provider });
          return (async () => {
            try {
              const response: Response = await Reflect.apply(target, thisArg, values);
              record({
                phase: "response_headers",
                request,
                elapsedMs: Math.round(performance.now() - started),
                status: response.status,
                provider,
                responseEncoding: ["gzip", "deflate", "br", "zstd"].includes(
                  response.headers.get("content-encoding") ?? "",
                )
                  ? response.headers.get("content-encoding")
                  : "identity_or_other",
                requestIdSha256: response.headers.has("x-request-id")
                  ? createHash("sha256").update(response.headers.get("x-request-id")!).digest("hex")
                  : null,
              });
              observeBody(
                response,
                (data) => record({ request, provider, ...data }),
                () => Math.round(performance.now() - started),
                init?.signal ?? (input instanceof Request ? input.signal : null),
              );
              return response;
            } catch (error) {
              record({
                phase: "fetch_error",
                request,
                elapsedMs: Math.round(performance.now() - started),
                ...safeFailure(error),
              });
              throw error;
            }
          })();
        },
      });
      globalThis.fetch = wrapped;
      restore = () => {
        if (globalThis.fetch === wrapped) globalThis.fetch = original;
      };
      const bun = (globalThis as unknown as { Bun?: { version: string } }).Bun;
      write({
        phase: "enabled",
        runtime: bun ? "bun" : "other",
        runtimeVersion: bun?.version ?? null,
        nativeFetch: Function.prototype.toString.call(original).includes("[native code]"),
      });
      ctx.ui.notify(
        `Safe network diagnostics enabled: ${logPath}. No headers, URLs or content are recorded.`,
        "info",
      );
    },
  });
  pi.on("message_end", (event) => {
    const message = event.message as { role?: string; errorMessage?: string };
    if (message.role === "assistant" && message.errorMessage) {
      write({ phase: "assistant_error", ...safeFailure({ message: message.errorMessage }) });
    }
  });
  pi.on("session_before_compact", (event) => {
    write({ phase: "compaction_start", reason: event.reason });
  });
  pi.on("session_compact", (event) => {
    write({ phase: "compaction_end", reason: event.reason, success: true });
  });
  pi.on("session_compact_failed", (event) => {
    write({
      phase: "compaction_end",
      reason: event.reason,
      success: false,
      aborted: event.aborted,
      ...safeFailure({ message: event.errorMessage }),
    });
  });
  pi.on("session_shutdown", stop);
}
