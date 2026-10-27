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
      const result = await ctx.modelRegistry
        .streamSimple(
          model,
          { messages: [{ role: "user", content: "Synthetic fixture", timestamp: 0 }] },
          {
            sessionId: sessionId ?? undefined,
            reasoning: "low",
            cacheRetention: testCase.cacheRetention,
            headers: { ...testCase.headers, "X-Fixture-Probe": "1" },
          },
        )
        .result();
      if (result.stopReason === "error") throw new Error(result.errorMessage);
    }
    ctx.shutdown();
  });
}
