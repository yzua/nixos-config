// Exercise actual request options while a different provider is selected in the root session.
import { readFileSync } from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => {
    const testCase = JSON.parse(readFileSync(process.env.PI_CACHE_CASE!, "utf8"));
    const model = ctx.modelRegistry.find(testCase.provider ?? "codex-lb", "fixture")!;
    if (model.contextWindow !== 123456 || model.maxTokens !== 100) {
      throw new Error("Provider registration replaced configured model metadata");
    }
    for (const sessionId of testCase.sessionIds ?? ["fixture-session"]) {
      const abort = new AbortController();
      const timer = testCase.abortMs === undefined ? undefined
        : setTimeout(() => abort.abort(), testCase.abortMs);
      const pending = ctx.modelRegistry
        .streamSimple(
          model,
          { messages: [{ role: "user", content: "Synthetic fixture", timestamp: 0 }] },
          {
            sessionId: sessionId === "@current" ? ctx.sessionManager.getSessionId() : sessionId ?? undefined,
            reasoning: "low",
            cacheRetention: testCase.cacheRetention,
            headers: { ...testCase.headers, "X-Fixture-Probe": "1" },
            signal: abort.signal,
            timeoutMs: testCase.timeoutMs,
            websocketConnectTimeoutMs: testCase.connectTimeoutMs,
            env: testCase.env,
            onPayload: testCase.payload !== undefined ? (payload) => testCase.replacePayload
              ? testCase.payload : { ...payload, ...testCase.payload } : undefined,
            onResponse: testCase.responseHookError ? () => { throw new Error("Fixture response hook failed"); } : undefined,
            onProviderStreamEvent: testCase.eventHookError ? () => { throw new Error("Fixture event hook failed"); } : undefined,
          },
        )
        .result();
      if (testCase.abortOnHandshake) {
        const barrier = await fetch(`${model.baseUrl}/fixture-ready`).then((response) => response.json());
        if (!barrier.ready) throw new Error("Handshake did not begin");
        abort.abort();
      }
      const result = await pending;
      clearTimeout(timer);
      if (testCase.expectClose || testCase.expectCloseFrame) {
        const barrier = await fetch(`${model.baseUrl}/fixture-closed`).then((response) => response.json());
        if (!barrier.ready || (testCase.expectCloseFrame && !barrier.close_frame)) {
          throw new Error("Socket was not closed before probe shutdown");
        }
      }
      if (testCase.expectedAbort) {
        if (result.stopReason !== "aborted") throw new Error(`Expected abort; got ${result.stopReason}`);
      } else if (testCase.expectedError) {
        if (!["error", "aborted"].includes(result.stopReason) || !result.errorMessage?.includes(testCase.expectedError)) {
          throw new Error(`Expected ${testCase.expectedError}; got ${result.stopReason}: ${result.errorMessage}`);
        }
      } else if (result.stopReason === "error" || result.stopReason === "aborted") {
        throw new Error(result.errorMessage);
      } else if (result.usage.input !== 10 || result.usage.output !== 2 ||
                 !result.content.some((part) => part.type === "text" && part.text === "fixture done")) {
        throw new Error("Responses text or usage was not preserved");
      }
    }
    ctx.shutdown();
  });
}
