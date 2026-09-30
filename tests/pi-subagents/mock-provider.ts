import { createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { appendFileSync, existsSync } from "node:fs";

export default function (pi: ExtensionAPI) {
  const scenario = process.env.PI_TEST_SCENARIO;
  const events = process.env.PI_TEST_EVENTS!;
  const session = process.env.PI_SUBAGENT_SESSION!;
  let calls = 0;

  const log = (event: string) =>
    appendFileSync(
      events,
      `${JSON.stringify({ event, sidecar: existsSync(`${session}.exit`) })}\n`,
    );

  if (scenario === "nested") {
    const globals = globalThis as Record<symbol, unknown>;
    globals[Symbol.for("pi-subagents/running-children-count")] = () => (calls === 1 ? 1 : 0);
  }

  pi.registerProvider("pi-test", {
    baseUrl: "http://127.0.0.1:9",
    apiKey: "unused-offline-test-key",
    api: "pi-test-api",
    models: [
      {
        id: "offline",
        name: "Offline regression fixture",
        reasoning: true,
        input: ["text"],
        contextWindow: 100_000,
        maxTokens: 4096,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      },
    ],
    streamSimple(model) {
      calls++;
      log(`provider_call:${calls}`);
      const failed = scenario === "exhausted" || (scenario === "recovered" && calls === 1);
      const question = scenario === "question" && calls === 1;
      const content = failed
        ? []
        : question
          ? [
              {
                type: "toolCall",
                id: "fixture-question",
                name: "ask_question",
                arguments: { question: "Which fixture value?" },
              },
            ]
          : [{ type: "text", text: "OFFLINE_RECOVERED" }];
      const message = {
        role: "assistant",
        api: model.api,
        provider: model.provider,
        model: model.id,
        timestamp: Date.now(),
        content,
        usage: {
          input: 1,
          output: 1,
          cacheRead: 0,
          cacheWrite: 0,
          totalTokens: 2,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
        },
        stopReason: failed ? "error" : question ? "toolUse" : "stop",
        ...(failed ? { errorMessage: "overloaded_error" } : {}),
      };
      const stream = createAssistantMessageEventStream();
      const deliver = () => {
        stream.push(
          failed
            ? { type: "error", reason: "error", error: message }
            : { type: "done", reason: message.stopReason, message },
        );
        stream.end();
      };
      if (scenario === "queued" && calls === 1) setTimeout(deliver, 100);
      else queueMicrotask(deliver);
      return stream;
    },
  });

  for (const event of ["agent_end", "agent_settled", "session_shutdown"] as const) {
    pi.on(event, () => log(event));
  }
}
