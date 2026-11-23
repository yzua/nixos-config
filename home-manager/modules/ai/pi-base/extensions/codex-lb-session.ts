// Preserve Codex-LB affinity and explicit Daybreak selection for proxy/direct providers.
import { createProvider, openAICodexResponsesApi, openAIResponsesApi } from "@earendil-works/pi-ai/compat";
import { builtinProviders } from "@earendil-works/pi-ai/providers/all";
import type { SimpleStreamOptions } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// Keep Pi's Responses serializer/parser; adapt only Daybreak's wire transport.
// The native Codex adapter requires an OAuth JWT and can fall back to HTTP,
// neither of which matches a restricted Codex-LB client key.
function daybreakTransport(options?: SimpleStreamOptions): { fetch: typeof fetch; close: () => void } {
  let close = () => {};
  const websocketFetch: typeof fetch = async (input, init) => {
    const request = new Request(input, init);
    const url = new URL(request.url);
    if (request.method !== "POST" || !url.pathname.endsWith("/responses")) {
      return daybreakError("only direct Responses WebSocket requests are supported");
    }
    if (url.protocol !== "https:" && url.protocol !== "http:") {
      return daybreakError("unsupported endpoint protocol");
    }
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    const payload = JSON.parse(await request.text());
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      return daybreakError("invalid Responses payload");
    }
    // Bun WebSocket does not inherit Pi's HTTP proxy settings. Fail closed
    // rather than silently bypass a configured proxy (including provider env).
    if (["HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"].some(
      (name) => options?.env?.[name] ?? process.env[name],
    )) return daybreakError("configured proxies are not supported by this WebSocket connector");
    // Enforce the contract after sampling parameters and payload hooks. These
    // request already-approved access; they never grant upstream authorization.
    payload.type = "response.create";
    payload.store = false;
    payload.access_programs = { ...payload.access_programs, cyber: "daybreak_blue" };
    const headers = new Headers(request.headers);
    headers.set("X-Codex-LB-Required-Capability", "trusted_cyber");
    for (const name of ["content-type", "content-length", "accept", "connection"]) headers.delete(name);
    const signals = [request.signal];
    if (options?.signal && options.signal !== request.signal) signals.push(options.signal);
    if (signals.some((signal) => signal.aborted)) throw new Error("Codex Daybreak: cancelled");

    return new Promise<Response>((resolve) => {
      let socket: WebSocket | undefined;
      let controller: ReadableStreamDefaultController<Uint8Array>;
      let sent = false;
      let opened = false;
      let finished = false;
      let timer: ReturnType<typeof setTimeout> | undefined;
      const encoder = new TextEncoder();
      const stream = new ReadableStream<Uint8Array>({
        start(value) { controller = value; },
        cancel() { finish(); },
      });
      function finish() {
        if (finished) return;
        finished = true;
        clearTimeout(timer);
        for (const signal of signals) signal.removeEventListener("abort", abort);
        if (socket) {
          socket.removeEventListener("open", open);
          socket.removeEventListener("message", message);
          socket.removeEventListener("error", failure);
          socket.removeEventListener("close", failure);
          try { socket.close(1000, "done"); } catch { /* Already closed. */ }
        }
      }
      close = () => {
        if (finished) return;
        controller.close();
        finish();
      };
      function fail(reason: string) {
        if (finished) return;
        // Do not leak handshake bodies/credentials or advertise an interrupted
        // submission as a retryable network error: delivery may be uncertain.
        const detail = `${reason}${sent ? "; delivery unknown, not replayed" : ""}`;
        const error = new Error(`Codex Daybreak: ${detail}`);
        if (opened) controller.error(error);
        else {
          controller.close();
          // Rejecting fetch would let the OpenAI SDK hide this behind its
          // retryable "Connection error". Return an explicit local 400 instead.
          resolve(daybreakError(detail));
        }
        finish();
      }
      function deadline(ms: number, reason: string) {
        clearTimeout(timer);
        if (ms > 0) timer = setTimeout(() => fail(reason), ms);
      }
      function abort() { fail("cancelled"); }
      function failure() { fail(sent ? "WebSocket interrupted" : "WebSocket handshake failed; no HTTP fallback"); }
      function open() {
        if (finished || !socket) return;
        try {
          sent = true;
          socket.send(JSON.stringify(payload));
          opened = true;
          // This Response is an in-process SSE facade, not an HTTP request.
          resolve(new Response(stream, { headers: {
            "content-type": "text/event-stream", "x-pi-transport": "websocket",
          } }));
          deadline(options?.timeoutMs ?? 300_000, "WebSocket idle deadline exceeded");
        } catch { failure(); }
      }
      function message(event: MessageEvent) {
        if (finished) return;
        try {
          const text = typeof event.data === "string"
            ? event.data : new TextDecoder().decode(event.data);
          const data = JSON.parse(text);
          if (!data || typeof data.type !== "string") throw new Error("Invalid event");
          if (data.type === "response.done") data.type = "response.completed";
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
          if (["response.completed", "response.failed", "response.incomplete", "error"].includes(data.type)) {
            controller.close();
            finish();
          } else deadline(options?.timeoutMs ?? 300_000, "WebSocket idle deadline exceeded");
        } catch { fail("invalid WebSocket event"); }
      }
      try {
        // Pi's managed executable runs Bun, whose WebSocket constructor accepts
        // authenticated headers. No global fetch/WebSocket patch or HTTP fallback.
        if (!process.versions.bun) throw new Error("Bun required");
        const Client = WebSocket as unknown as new (
          url: string, options: { headers: Record<string, string> },
        ) => WebSocket;
        socket = new Client(url.toString(), { headers: Object.fromEntries(headers) });
        socket.binaryType = "arraybuffer";
        socket.addEventListener("open", open);
        socket.addEventListener("message", message);
        socket.addEventListener("error", failure);
        socket.addEventListener("close", failure);
        for (const signal of signals) signal.addEventListener("abort", abort, { once: true });
        deadline(options?.websocketConnectTimeoutMs ?? 15_000, "WebSocket handshake deadline exceeded");
        if (signals.some((signal) => signal.aborted)) abort();
      } catch { fail("WebSocket unavailable; no HTTP fallback"); }
    });
  };
  return { fetch: websocketFetch, close: () => close() };
}

function daybreakError(message: string): Response {
  return Response.json({ error: {
    code: "daybreak_transport_error", type: "invalid_request_error",
    message: `Codex Daybreak: ${message}`,
  } }, { status: 400 });
}

function directDaybreakOptions(options?: SimpleStreamOptions): SimpleStreamOptions {
  return {
    ...options,
    // Native Codex aliases normalize replayed tool IDs. Send full transcripts,
    // not connection-scoped previous_response_id deltas with the original IDs.
    transport: "websocket",
    onPayload: async (payload, model) => {
      const replacement = await options?.onPayload?.(payload, model);
      const body = replacement === undefined ? payload : replacement;
      if (!body || typeof body !== "object" || Array.isArray(body)) {
        throw new Error("Direct Daybreak: invalid Responses payload");
      }
      if ("previous_response_id" in body) {
        throw new Error("Direct Daybreak: previous_response_id is unsupported; provide full history");
      }
      const programs = (body as { access_programs?: Record<string, unknown> }).access_programs;
      return { ...body, store: false, access_programs: { ...programs, cyber: "daybreak_blue" } };
    },
  };
}

export default function (pi: ExtensionAPI) {
  const codex = builtinProviders().find((provider) => provider.id === "openai-codex");
  const sol = codex?.getModels().find((model) => model.id === "gpt-6-sol");
  if (codex && sol) {
    const native = openAICodexResponsesApi();
    pi.registerProvider(createProvider<"openai-codex-responses">({
      id: "codex-cyber-daybreak",
      name: "OpenAI direct · Daybreak Blue",
      baseUrl: codex.baseUrl,
      auth: codex.auth,
      // Pi's composer dispatches to native methods only for APIs present in the
      // baseline catalog. Keep Sol here; models.json can override its metadata.
      models: [{ ...sol, provider: "codex-cyber-daybreak" }],
      api: {
        ...native,
        stream: (model, context, options) => native.stream(model, context, directDaybreakOptions(options)),
        streamSimple: (model, context, options) => native.streamSimple(model, context, directDaybreakOptions(options)),
      },
    }));
  } else {
    // A missing direct model must not disable the independent proxy providers.
    console.warn("Direct Daybreak unavailable: Pi's native OpenAI Codex Sol model is missing");
  }

  // Override only these providers' generic Responses adapter. Keep their configured
  // models, endpoint and authentication; use each request's identity, not the
  // root session's model/ID (nested requests may belong to another session).
  for (const provider of ["codex-lb", "codex-daybreak"]) {
    pi.registerProvider(provider, {
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

        // Delegate serialization, streaming and usage to Pi. A null or
        // explicitly supplied alias is an intentional override and stays intact.
        const transport = provider === "codex-daybreak" ? daybreakTransport(options) : undefined;
        return openAIResponsesApi().streamSimple(model, context, {
          ...options,
          headers: addAlias ? { ...headers, "session-id": sessionId } : headers,
          ...(transport ? {
            fetch: transport.fetch,
            maxRetries: 0,
            onResponse: async (...args) => {
              try { await options?.onResponse?.(...args); }
              catch (error) { transport.close(); throw error; }
            },
            onProviderStreamEvent: async (...args) => {
              try { await options?.onProviderStreamEvent?.(...args); }
              catch (error) { transport.close(); throw error; }
            },
          } : {}),
        });
      },
    });
  }
}
