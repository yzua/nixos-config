import { createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { appendFileSync, readFileSync } from "node:fs";

// Emit a deterministic tool call through Pi's real validation/execution path.
// This provider never opens a network connection or reads authentication.
export default function (pi: ExtensionAPI) {
  const fixture = JSON.parse(readFileSync(process.env.PI_EXTENSION_CASE!, "utf8"));
  const eventLog = process.env.PI_EXTENSION_EVENTS;
  if (eventLog) {
    pi.events.on("herdr:blocked", (event) => {
      appendFileSync(eventLog, JSON.stringify(event) + "\n");
    });
  }
  pi.registerProvider("extension-test", {
    baseUrl: "http://127.0.0.1:9",
    apiKey: "unused-offline-fixture",
    api: "extension-test-api",
    models: [
      {
        id: "offline",
        name: "Offline extension fixture",
        reasoning: false,
        input: ["text"],
        contextWindow: 100_000,
        maxTokens: 1024,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      },
    ],
    streamSimple(model, context) {
      const first = context.messages.at(-1)?.role === "user";
      const message = {
        role: "assistant" as const,
        api: model.api,
        provider: model.provider,
        model: model.id,
        timestamp: Date.now(),
        content: first
          ? [
              {
                type: "toolCall" as const,
                id: "extension-fixture-call",
                name: fixture.tool,
                arguments: fixture.arguments,
              },
            ]
          : [{ type: "text" as const, text: "EXTENSION_FIXTURE_DONE" }],
        usage: {
          input: 1,
          output: 1,
          cacheRead: 0,
          cacheWrite: 0,
          totalTokens: 2,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
        },
        stopReason: first ? ("toolUse" as const) : ("stop" as const),
      };
      const stream = createAssistantMessageEventStream();
      queueMicrotask(() => {
        stream.push({ type: "done", reason: message.stopReason, message });
        stream.end();
      });
      return stream;
    },
  });
}
