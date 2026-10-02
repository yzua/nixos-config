/** Fixed-model, owned Flash delegation for the root pi-re profile only; not a sandbox. */
import { spawn, type ChildProcess } from "node:child_process";
import { readFile } from "node:fs/promises";
import * as path from "node:path";
import { Type } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const RESULT_BYTES = 16 * 1024;
const active = new Set<ChildProcess>();

function stateDirectory(): string {
  const home = process.env.HOME;
  if (!home || !path.isAbsolute(home)) throw new Error("Absolute HOME is required for pi-re");
  const state = process.env.XDG_STATE_HOME || path.join(home, ".local/state");
  const data = process.env.XDG_DATA_HOME || path.join(home, ".local/share");
  if (!path.isAbsolute(state) || !path.isAbsolute(data))
    throw new Error("Absolute RE XDG paths are required");
  if (process.env.PI_CODING_AGENT_DIR !== path.join(data, "pi-re/agent")) {
    throw new Error("re_subagent is restricted to the independent RE profile");
  }
  return path.join(state, "pi-re");
}

export default function (pi: ExtensionAPI) {
  // Defense in depth even if a child is accidentally given this explicit resource.
  if (process.env.PI_RE_CHILD === "1") return;

  pi.on("session_shutdown", () => {
    for (const child of active) child.kill("SIGTERM");
  });

  pi.registerTool({
    name: "re_subagent",
    label: "RE Flash subagent",
    exposure: "model-only",
    description:
      "Delegate one bounded, explicitly authorized RE task to zai/glm-5.3-flash (high thinking). " +
      "Fresh native session, reviewed RE resources, 180-second deadline, at most two children, " +
      "16 KiB summary with private artifact references. No resume or nested delegation. " +
      "Supply current engagement scope, approved inputs, resource ownership and stop conditions in task. " +
      "One writer per checkout/device/browser/project. Runs on the host, NOT in a sandbox; " +
      "do not delegate unknown executable samples without an approved whole-process lab boundary.",
    parameters: Type.Object(
      {
        task: Type.String({
          minLength: 1,
          maxLength: 65536,
          description: "Authorized task and current scope; no implicit parent history",
        }),
        cwd: Type.Optional(
          Type.String({
            description: "Existing absolute working directory; defaults to caller cwd",
          }),
        ),
      },
      { additionalProperties: false },
    ),

    async execute(_id, params, signal, _onUpdate, ctx) {
      if (process.env.PI_RE_CHILD === "1") throw new Error("RE children cannot delegate");
      if (signal?.aborted) throw new Error("RE delegation cancelled before launch");
      if (active.size >= 2) throw new Error("At most two RE children may run concurrently");
      if (
        Buffer.byteLength(params.task, "utf8") > 65536 ||
        !params.task.trim() ||
        params.task.includes("\0")
      ) {
        throw new Error("Task must be nonempty UTF-8 text of at most 64 KiB without NUL");
      }
      const state = stateDirectory();
      const configPath = process.env.PI_RE_CONFIG;
      if (!configPath || !path.isAbsolute(configPath))
        throw new Error("Absolute PI_RE_CONFIG is required");
      const cwd = params.cwd ?? ctx.cwd;
      if (!path.isAbsolute(cwd)) throw new Error("RE child cwd must be absolute");
      // Generated public config only: never inspect profile settings or credentials.
      const rawConfig = await readFile(configPath, "utf8");
      if (Buffer.byteLength(rawConfig, "utf8") > 1024 * 1024)
        throw new Error("RE config exceeds size limit");
      const config = JSON.parse(rawConfig) as { python: string; resources: string };
      if (
        typeof config.python !== "string" ||
        !path.isAbsolute(config.python) ||
        typeof config.resources !== "string" ||
        !path.isAbsolute(config.resources)
      ) {
        throw new Error("RE config requires absolute Python and reviewed resource paths");
      }
      // Calls can race at the await above. Reserve again immediately before spawn.
      if (active.size >= 2) throw new Error("At most two RE children may run concurrently");
      if (signal?.aborted) throw new Error("RE delegation cancelled before launch");
      const environment = { ...process.env };
      for (const name of [
        "PI_SESSION_FILE",
        "PI_SESSION_ID",
        "PI_PROVIDER",
        "PI_MODEL",
        "PI_REASONING_LEVEL",
        "PI_CODING_AGENT_SESSION_DIR",
        "PI_RE_CHILD_SESSION_DIR",
      ]) {
        delete environment[name];
      }
      const child = spawn(
        config.python,
        [
          path.join(config.resources, "subagent.py"),
          "--config",
          configPath,
          "--state-dir",
          state,
          "--cwd",
          cwd,
        ],
        {
          cwd,
          env: environment,
          shell: false,
          stdio: ["pipe", "pipe", "pipe"],
        },
      );
      active.add(child);
      let cancelTimer: ReturnType<typeof setTimeout> | undefined;
      const cancel = () => {
        child.kill("SIGTERM"); // Helper relays to its owned process group; never global kill.
        cancelTimer ??= setTimeout(() => child.kill("SIGKILL"), 3000);
      };
      signal?.addEventListener("abort", cancel, { once: true });
      // Failsafe in addition to the helper's 180s deadline, allowing bounded cleanup.
      const deadline = setTimeout(cancel, 181000);
      try {
        const stdout = await new Promise<Buffer>((resolve, reject) => {
          const chunks: Buffer[] = [];
          let bytes = 0;
          let overflow = false;
          child.stdout.on("data", (chunk: Buffer) => {
            bytes += chunk.length;
            if (bytes > RESULT_BYTES + 1) {
              overflow = true;
              cancel();
            } else chunks.push(chunk);
          });
          // Drain diagnostics, never forward unbounded or private raw logs.
          child.stderr.on("data", () => {});
          child.stdin.on("error", () => {}); // Early blocked child can close stdin.
          child.on("error", reject);
          child.on("close", () => {
            if (overflow) reject(new Error("RE helper exceeded the 16 KiB result budget"));
            else resolve(Buffer.concat(chunks));
          });
          child.stdin.end(params.task, "utf8");
          if (signal?.aborted) cancel();
        });
        const summary = JSON.parse(stdout.toString("utf8"));
        if (
          !summary ||
          typeof summary !== "object" ||
          summary.model !== "glm-5.3-flash" ||
          summary.provider !== "zai" ||
          !["ok", "partial", "blocked", "error", "timeout", "cancelled"].includes(summary.status)
        ) {
          throw new Error("Invalid RE helper summary");
        }
        const text = JSON.stringify(summary);
        if (Buffer.byteLength(text, "utf8") > RESULT_BYTES)
          throw new Error("RE summary exceeds 16 KiB");
        return {
          content: [{ type: "text", text }],
          details: summary,
          usage: summary.usage,
          isError: !["ok", "partial"].includes(summary.status),
        };
      } finally {
        clearTimeout(deadline);
        if (cancelTimer) clearTimeout(cancelTimer);
        signal?.removeEventListener("abort", cancel);
        active.delete(child);
      }
    },
  });
}
