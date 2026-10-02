// Offline-only loader: no installed Pi packages, mux CLI, or provider access.
const fixture = (name) => new URL(name, import.meta.url).href;
export async function resolve(specifier, context, nextResolve) {
  if (specifier === "node:fs" && context.parentURL?.endsWith("/managed-run.ts")) {
    return { url: fixture("fs-stubs.mjs"), shortCircuit: true };
  }
  if (specifier === "node:fs" && context.parentURL?.endsWith("/session.ts")) {
    return { url: fixture("proc-stubs.mjs"), shortCircuit: true };
  }
  if (specifier === "node:child_process" || specifier === "child_process") {
    return { url: fixture("forbidden-process.mjs"), shortCircuit: true };
  }
  if (specifier.endsWith("/tmux.ts") || specifier === "./tmux.ts") {
    return { url: fixture("mux.mjs"), shortCircuit: true };
  }
  if (specifier.endsWith("/herdr.ts") || specifier === "./herdr.ts") {
    return { url: fixture("mux.mjs"), shortCircuit: true };
  }
  if (["@mariozechner/pi-coding-agent", "@mariozechner/pi-tui", "@sinclair/typebox"].includes(specifier)) {
    return { url: fixture("pi-stubs.mjs"), shortCircuit: true };
  }
  return nextResolve(specifier, context);
}
