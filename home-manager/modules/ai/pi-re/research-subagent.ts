/** Root-only named research turns, with exclusive native-session resume and finite budgets. */
import { spawn, type ChildProcess } from "node:child_process";
import { readFile } from "node:fs/promises";
import * as path from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const active = new Set<ChildProcess>();
const common = {
  name: Type.String({
    pattern: "^[a-z][a-z0-9_-]{0,47}$",
    description: "Parent-scoped persistent worker name",
  }),
  timeout_seconds: Type.Optional(
    Type.Integer({
      minimum: 1,
      maximum: 3600,
      description:
        "Finite turn budget; defaults to configured 600 seconds, subject to the configured ceiling",
    }),
  ),
};

export default function (pi: ExtensionAPI) {
  if (process.env.PI_RE_CHILD === "1" || process.env.PI_RE_RESEARCH === "1") return;
  pi.on("session_shutdown", () => {
    for (const child of active) child.kill("SIGTERM");
  });

  async function run(
    name: string,
    task: string,
    ctx: ExtensionContext,
    signal: AbortSignal | undefined,
    resume: boolean,
    cwd?: string,
    timeout?: number,
  ) {
    const home = process.env.HOME;
    const data = process.env.XDG_DATA_HOME || (home && path.join(home, ".local/share"));
    const state = process.env.XDG_STATE_HOME || (home && path.join(home, ".local/state"));
    const configPath = process.env.PI_RE_CONFIG;
    const parent = ctx.sessionManager.getSessionFile();
    if (
      !home ||
      !data ||
      !state ||
      process.env.PI_PROFILE !== "pi-re" ||
      !configPath ||
      !parent ||
      ![data, state, configPath, parent].every(path.isAbsolute) ||
      process.env.PI_CODING_AGENT_DIR !== path.join(home, ".pi/agent")
    ) {
      throw new Error("Research delegation requires a persisted root RE session");
    }
    if (signal?.aborted) throw new Error("Research cancelled before launch");
    if (!task.trim() || task.includes("\0") || Buffer.byteLength(task) > 65536) {
      throw new Error("Research input must be nonempty text of at most 64 KiB");
    }
    const raw = await readFile(configPath, "utf8");
    if (Buffer.byteLength(raw) > 1024 * 1024) throw new Error("Research config exceeds budget");
    const config = JSON.parse(raw) as {
      python: string;
      resources: string;
      research?: { maxTimeoutSeconds?: number };
    };
    if (!path.isAbsolute(config.python) || !path.isAbsolute(config.resources)) {
      throw new Error("Pinned research paths must be absolute");
    }
    const args = [
      path.join(config.resources, "research.py"),
      "--config",
      configPath,
      "--state-dir",
      path.join(state, "pi-re"),
      "--parent",
      parent,
      "--name",
      name,
    ];
    if (resume) args.push("--resume");
    else args.push("--cwd", cwd ?? ctx.cwd);
    if (timeout !== undefined) args.push("--timeout", String(timeout));
    const environment = { ...process.env };
    for (const key of Object.keys(environment)) {
      if (key.startsWith("HERDR_") || key.startsWith("TMUX") || key.startsWith("PI_SUBAGENT"))
        delete environment[key];
    }
    const child = spawn(config.python, args, {
      env: environment,
      shell: false,
      stdio: ["pipe", "pipe", "pipe"],
    });
    active.add(child);
    let escalation: ReturnType<typeof setTimeout> | undefined;
    const cancel = () => {
      child.kill("SIGTERM");
      escalation ??= setTimeout(() => child.kill("SIGKILL"), 3000);
    };
    signal?.addEventListener("abort", cancel, { once: true });
    // Helper owns the actual policy/deadline; this is only a bounded cleanup backstop.
    const failsafe = setTimeout(cancel, 3605 * 1000);
    try {
      const result = await new Promise<Buffer>((resolve, reject) => {
        const chunks: Buffer[] = [];
        let bytes = 0;
        let overflow = false;
        child.stdout.on("data", (chunk: Buffer) => {
          bytes += chunk.length;
          if (bytes > 16385) {
            overflow = true;
            cancel();
          } else chunks.push(chunk);
        });
        child.stderr.on("data", () => {});
        child.stdin.on("error", () => {});
        child.on("error", reject);
        child.on("close", () =>
          overflow
            ? reject(new Error("Research summary exceeded budget"))
            : resolve(Buffer.concat(chunks)),
        );
        child.stdin.end(task, "utf8");
        if (signal?.aborted) cancel();
      });
      const summary = JSON.parse(result.toString("utf8"));
      if (
        !summary ||
        summary.name !== name ||
        !["ok", "partial", "blocked", "error", "timeout", "cancelled"].includes(summary.status)
      ) {
        throw new Error("Invalid research result");
      }
      return {
        content: [{ type: "text" as const, text: JSON.stringify(summary) }],
        details: summary,
        usage: summary.usage,
        isError: !["ok", "partial"].includes(summary.status),
      };
    } finally {
      clearTimeout(failsafe);
      if (escalation) clearTimeout(escalation);
      signal?.removeEventListener("abort", cancel);
      active.delete(child);
    }
  }

  pi.registerTool({
    name: "research_subagent",
    label: "Named research worker",
    exposure: "model-only",
    description:
      "Start a named documentation/source-review worker. Up to four concurrent workers across the RE profile; finite configurable turn budgets. Only bounded source-reading and web search/fetch tools, no shell/edit/device/MCP/nested delegation. State is private and parent-scoped. Returns a summary when this turn ends; resume completed turns with research_subagent_message.",
    parameters: Type.Object(
      {
        ...common,
        task: Type.String({ minLength: 1, maxLength: 65536 }),
        cwd: Type.Optional(
          Type.String({
            description: "Specific approved absolute source directory; pinned for all follow-ups",
          }),
        ),
      },
      { additionalProperties: false },
    ),
    execute(_id, params, signal, _update, ctx) {
      return run(params.name, params.task, ctx, signal, false, params.cwd, params.timeout_seconds);
    },
  });
  pi.registerTool({
    name: "research_subagent_message",
    label: "Resume research worker",
    exposure: "model-only",
    description:
      "Resume a completed named research worker with a follow-up in its existing native session. Keeps the original source root and read-only tools. Only new-turn output is returned. A live/unknown writer or changed loadout blocks resume; this is not steering a running worker.",
    parameters: Type.Object(
      { ...common, message: Type.String({ minLength: 1, maxLength: 65536 }) },
      { additionalProperties: false },
    ),
    execute(_id, params, signal, _update, ctx) {
      return run(params.name, params.message, ctx, signal, true, undefined, params.timeout_seconds);
    },
  });
}
