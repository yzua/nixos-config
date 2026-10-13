// Offline provider for exercising Pi's real error normalization and retry lifecycle.
import { type AssistantMessage, createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { appendFileSync, readFileSync } from "node:fs";

export default function (pi: ExtensionAPI) {
  const fixture = JSON.parse(readFileSync(process.env.PI_RETRY_CASE!, "utf8"));
  let calls = 0;
  pi.registerProvider("retry-test", {
    baseUrl: "http://127.0.0.1:9",
    apiKey: "unused-offline-fixture",
    api: "retry-test-api",
    models: [
      {
        id: "offline",
        name: "Offline retry fixture",
        reasoning: false,
        input: ["text"],
        contextWindow: 100_000,
        maxTokens: 1024,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      },
    ],
    streamSimple(model, context) {
      calls++;
      appendFileSync(
        process.env.PI_RETRY_CALLS!,
        JSON.stringify({ calls, messages: context.messages }) + "\n",
      );
      const failing = calls <= fixture.failures;
      const message: AssistantMessage = {
        role: "assistant",
        api: model.api,
        provider: model.provider,
        model: model.id,
        timestamp: Date.now(),
        content: [
          { type: "text", text: failing ? "PARTIAL_FIXTURE_OUTPUT" : "RETRY_FIXTURE_DONE" },
        ],
        usage: {
          input: 1,
          output: 1,
          cacheRead: 0,
          cacheWrite: 0,
          totalTokens: 2,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
        },
        stopReason: failing ? fixture.stopReason : "stop",
        ...(failing ? { errorMessage: fixture.error } : {}),
      };
      const stream = createAssistantMessageEventStream();
      queueMicrotask(() => {
        if (message.stopReason === "error" || message.stopReason === "aborted") {
          stream.push({ type: "error", reason: message.stopReason, error: message });
        } else {
          stream.push({ type: "done", reason: "stop", message });
        }
        stream.end();
      });
      return stream;
    },
  });
}
