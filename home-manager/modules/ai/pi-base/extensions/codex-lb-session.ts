// Preserve Codex-LB session affinity across gateways that drop underscore headers.
import { openAIResponsesApi } from "@earendil-works/pi-ai/compat";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  // Override only this provider's generic Responses adapter. Keep its configured
  // models, endpoint and authentication; use each request's identity, not the
  // root session's model/ID (nested requests may belong to another session).
  pi.registerProvider("codex-lb", {
    api: "openai-responses",
    streamSimple(model, context, options) {
      const headers = options?.headers ?? {};
      const entries = Object.entries(headers);
      const explicitAlias = entries.some(([name]) => name.toLowerCase() === "session-id");
      const nativeHeader = entries.find(([name]) => name.toLowerCase() === "session_id");
      const sessionId = nativeHeader ? nativeHeader[1] : options?.sessionId;
      const addAlias =
        options?.cacheRetention !== "none" &&
        !explicitAlias &&
        typeof sessionId === "string" &&
        sessionId.trim().length > 0;

      // Delegate serialization, streaming, retries and usage to Pi. A null or
      // explicitly supplied alias is an intentional override and stays intact.
      return openAIResponsesApi().streamSimple(model, context, {
        ...options,
        headers: addAlias ? { ...headers, "session-id": sessionId } : headers,
      });
    },
  });
}
