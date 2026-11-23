// Verify native Codex alias reasoning/tool replay through both public request paths.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => {
    const model = ctx.modelRegistry.find("codex-cyber-daybreak", "fixture")!;
    const first = await ctx.modelRegistry.streamSimple(model, {
      messages: [{ role: "user", content: "Synthetic fixture", timestamp: 0 }],
    }, {
      sessionId: ctx.sessionManager.getSessionId(),
      reasoning: "low",
      headers: { "X-Fixture-Probe": "1" },
      transport: "websocket-cached", // The alias must enforce full-transcript mode.
    }).result();
    const call = first.content.find((part) => part.type === "toolCall");
    if (first.stopReason !== "toolUse" || !call) throw new Error("Native tool call was not parsed");
    const second = await ctx.modelRegistry.complete(model, {
      messages: [
        { role: "user", content: "Synthetic fixture", timestamp: 0 },
        first,
        { role: "toolResult", toolCallId: call.id, toolName: call.name,
          content: [{ type: "text", text: "Synthetic tool result" }], isError: false, timestamp: 1 },
      ],
    }, {
      sessionId: ctx.sessionManager.getSessionId(),
      headers: { "X-Fixture-Probe": "1" },
      transport: "websocket-cached",
      onPayload: (payload) => ({ ...payload, access_programs: { cyber: "standard" } }),
    });
    if (second.stopReason !== "stop" || second.usage.input !== 10 || second.usage.output !== 2 ||
        !second.content.some((part) => part.type === "text" && part.text === "fixture done")) {
      throw new Error("Native tool roundtrip or usage failed");
    }
    ctx.shutdown();
  });
}
