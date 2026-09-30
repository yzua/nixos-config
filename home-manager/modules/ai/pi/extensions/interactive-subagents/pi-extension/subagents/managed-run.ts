import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmdirSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { randomUUID } from "node:crypto";
import { dirname, join, resolve } from "node:path";
import type { SubagentActivityState } from "./activity.ts";
import {
  countSessionEntryLines,
  findLastAssistantMessage,
  getNewEntries,
  getSessionId,
  summarizeSessionStats,
  type SessionStats,
  type SubagentLoadout,
} from "./session.ts";
import type { SubagentStatusState } from "./status.ts";
import {
  closeSurface,
  createSurface,
  pollForExit,
  readScreen,
  sendLongCommand,
  shellEscape,
} from "./tmux.ts";

export interface SubagentResult {
  name: string;
  task: string;
  summary: string;
  sessionFile?: string;
  sessionId?: string;
  claudeSessionId?: string;
  exitCode: number;
  elapsed: number;
  error?: string;
  errorMessage?: string;
  stats?: SessionStats;
}

export interface RunningSubagent {
  id: string;
  name: string;
  task: string;
  agent?: string;
  surface: string;
  startTime: number;
  sessionFile: string;
  launchScriptFile?: string;
  activityFile?: string;
  activity?: SubagentActivityState;
  activityRead?: {
    ok: boolean;
    reason?: "missing" | "invalid" | "wrong-id";
    error?: string;
  };
  abortController?: AbortController;
  cli?: string;
  sentinelFile?: string;
  statusState: SubagentStatusState;
  /** User-driven initial runs suppress status wakeups; resumes are autonomous. */
  interactive: boolean;
}

type ResultPolicy =
  | { kind: "initial" }
  | {
      kind: "resume";
      entryCountBefore: number;
      sessionId: string;
    };

type LaunchPlan = {
  launchScriptFile: string;
  scriptPreamble: string;
} & (
  | {
      kind: "pi";
      parts: string[];
      loadout: SubagentLoadout;
      autoExit: boolean;
    }
  | {
      kind: "command";
      command: string;
    }
);

export class RunOwnershipError extends Error {}

type SessionOwner = {
  version: 1;
  token: string;
  sessionFile: string;
  surface: string;
  mux: string;
};

/** Own a pane from creation through result delivery, regardless of session policy.
 * Callers prepare the session and sandbox; they never register or watch a run.
 * UI observation stays outside this module, but failures in it cannot leak a pane.
 */
export class ManagedRuns {
  readonly running = new Map<string, RunningSubagent>();
  private readonly owners = new WeakMap<RunningSubagent, SessionOwner>();

  // Locks serialize inspection and replacement across runtimes AND processes.
  // A crash during launch leaves an unknown lock: refuse, never guess it is safe.
  private lockSession(sessionFile: string): () => void {
    const lock = `${resolve(sessionFile)}.owner.lock`;
    mkdirSync(dirname(lock), { recursive: true });
    try {
      mkdirSync(lock);
    } catch {
      throw new RunOwnershipError(
        `Cannot safely resume: session ownership is busy or unknown (${lock}).`,
      );
    }
    return () => {
      try {
        rmdirSync(lock);
      } catch {
        // A leftover/unknown lock remains fail-closed. Cleanup failure must not
        // reject background supervision or prevent completion/error delivery.
      }
    };
  }

  private muxIdentity(): string {
    // The final TMUX field identifies the caller's session, not the server.
    return (process.env.TMUX ?? "").split(",").slice(0, 2).join(",");
  }

  private readOwner(sessionFile: string): SessionOwner | undefined {
    const file = `${resolve(sessionFile)}.owner.json`;
    try {
      const owner = JSON.parse(readFileSync(file, "utf8"));
      if (
        owner.version !== 1 ||
        typeof owner.token !== "string" ||
        !owner.token ||
        owner.sessionFile !== resolve(sessionFile) ||
        typeof owner.surface !== "string" ||
        !/^%\d+$/.test(owner.surface) ||
        typeof owner.mux !== "string" ||
        !owner.mux
      )
        throw new Error("invalid owner");
      return owner;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
      throw new RunOwnershipError(
        `Cannot safely resume: corrupt or unknown session ownership (${file}).`,
      );
    }
  }

  private async claimSession(sessionFile: string, signal: AbortSignal): Promise<() => void> {
    // Synchronous lock acquisition precedes the first await in any launch.
    const unlock = this.lockSession(sessionFile);
    try {
      const owner = this.readOwner(sessionFile);
      if (owner) {
        if (owner.mux !== this.muxIdentity()) {
          throw new RunOwnershipError(
            "Cannot safely resume: child belongs to another or unknown tmux server.",
          );
        }
        const probe = new AbortController();
        const probeSignal = AbortSignal.any([signal, probe.signal]);
        const timer = setTimeout(() => probe.abort(), 2600);
        let onAbort: (() => void) | undefined;
        try {
          // Probe terminal completion/pane loss only. An error sidecar can be
          // published before process exit, so it cannot release writer ownership.
          // Bound the caller even if an external tmux read is slow. A late
          // probe has no delivery hooks or authority to remove the claim.
          const exit = await Promise.race([
            pollForExit(owner.surface, probeSignal, { interval: 50 }),
            new Promise<never>((_resolve, reject) => {
              onAbort = () => reject(new Error("Ownership probe aborted"));
              if (probeSignal.aborted) onAbort();
              else probeSignal.addEventListener("abort", onAbort, { once: true });
            }),
          ]);
          if (
            exit.reason !== "sentinel" &&
            exit.errorMessage !==
              `Subagent pane ${owner.surface} disappeared before reporting completion.`
          )
            throw new Error("cannot establish child exit");
        } catch {
          throw new RunOwnershipError(
            "Cannot safely resume: a surviving child still owns this session, or its exit cannot be established.",
          );
        } finally {
          clearTimeout(timer);
          if (onAbort) probeSignal.removeEventListener("abort", onAbort);
        }
        try {
          closeSurface(owner.surface);
        } catch {
          /* Already closed. */
        }
        // Old error sidecars belong to the completed writer, not its successor.
        const exitFile = `${resolve(sessionFile)}.exit`;
        if (existsSync(exitFile)) unlinkSync(exitFile);
        unlinkSync(`${resolve(sessionFile)}.owner.json`);
      }
      if (signal.aborted) throw new Error("Aborted while claiming subagent session");
      return unlock;
    } catch (error) {
      unlock();
      throw error;
    }
  }

  /** Dispose supervision without surrendering a child's durable writer claim. */
  dispose(): void {
    this.running.clear();
  }

  constructor(
    private readonly hooks: {
      moduleSignal(): AbortSignal;
      shellReadyDelayMs(): number;
      refresh(started: boolean): void;
      tick(running: RunningSubagent): void;
      present(result: SubagentResult, name: string): string;
      sendMessage: ExtensionAPI["sendMessage"];
    },
  ) {}

  async launch(
    candidate: Omit<RunningSubagent, "surface" | "abortController">,
    policy: { kind: "initial" } | { kind: "resume"; sessionId: string },
    prepare: (running: RunningSubagent) => LaunchPlan,
    register?: (running: RunningSubagent) => void,
  ): Promise<RunningSubagent> {
    // Capture this runtime's signal, not whatever a later session installs.
    const moduleSignal = this.hooks.moduleSignal();
    const unlock = await this.claimSession(candidate.sessionFile, moduleSignal);
    let running: RunningSubagent | undefined;
    let resultPolicy: ResultPolicy;
    try {
      // Sample only after the previous writer has truly exited: any final
      // detached output is old history, never this follow-up's summary.
      resultPolicy =
        policy.kind === "resume"
          ? { ...policy, entryCountBefore: countSessionEntryLines(candidate.sessionFile) }
          : policy;
      const surface = createSurface(candidate.name);
      running = {
        ...candidate,
        surface,
        abortController: new AbortController(),
      };
      const owner: SessionOwner = {
        version: 1,
        token: randomUUID(),
        sessionFile: resolve(running.sessionFile),
        surface,
        mux: this.muxIdentity(),
      };
      this.owners.set(running, owner);
      // Persist the pane BEFORE dispatch: even parent death cannot hide a writer.
      writeFileSync(`${owner.sessionFile}.owner.json`, JSON.stringify(owner), { flag: "wx" });
      await new Promise<void>((resolve) => setTimeout(resolve, this.hooks.shellReadyDelayMs()));
      if (moduleSignal.aborted) throw new Error("Aborted while launching subagent");
      const plan = prepare(running);
      running.launchScriptFile = plan.launchScriptFile;
      const command = plan.kind === "pi" ? this.piCommand(running, plan) : plan.command;
      sendLongCommand(surface, `${command}; echo '__SUBAGENT_DONE_'$?'__'`, {
        scriptPath: plan.launchScriptFile,
        scriptPreamble: plan.scriptPreamble,
      });
      this.running.set(running.id, running);
      register?.(running);
      this.hooks.refresh(true);
    } catch (error) {
      if (running) this.release(running, true);
      throw error;
    } finally {
      unlock();
    }
    // The tool's signal ends with its acknowledgement. Supervision instead
    // belongs to this run and the extension runtime (shutdown or /reload).
    void this.complete(running, resultPolicy, moduleSignal);
    return running;
  }

  private piCommand(running: RunningSubagent, plan: Extract<LaunchPlan, { kind: "pi" }>): string {
    const { loadout } = plan;
    const env: Record<string, string | undefined> = {
      PI_CODING_AGENT_DIR: loadout.agentDir ?? process.env.PI_CODING_AGENT_DIR,
      PI_SUBAGENT_ALLOWED: loadout.spawnable?.length ? loadout.spawnable.join(",") : undefined,
      PI_SUBAGENT_AGENT: loadout.agent ?? undefined,
      PI_SUBAGENT_NAME: running.name,
      PI_SUBAGENT_SESSION: running.sessionFile,
      PI_SUBAGENT_ID: running.id,
      PI_SUBAGENT_ACTIVITY_FILE: running.activityFile,
      PI_SUBAGENT_SURFACE: running.surface,
      PI_SUBAGENT_AUTO_EXIT: plan.autoExit ? "1" : undefined,
    };
    const prefix = Object.entries(env)
      .filter((entry): entry is [string, string] => entry[1] !== undefined)
      .map(([key, value]) => `${key}=${shellEscape(value)}`)
      .join(" ");
    const cd = loadout.cwd ? `cd ${shellEscape(loadout.cwd)} && ` : "";
    return `${cd}${prefix} ${plan.parts.join(" ")}`;
  }

  private release(running: RunningSubagent, lockHeld = false): void {
    let closed = false;
    try {
      closeSurface(running.surface);
      closed = true;
    } catch {
      // Do not surrender ownership if cancellation/cleanup cannot kill the
      // writer. A later launch must establish actual terminal exit/pane loss.
    }
    if (this.running.get(running.id) === running) this.running.delete(running.id);
    if (!closed) return;
    let unlock: (() => void) | undefined;
    try {
      if (!lockHeld) unlock = this.lockSession(running.sessionFile);
      const owner = this.readOwner(running.sessionFile);
      // A late obsolete watcher must never unlink a successor's claim.
      if (owner?.token === this.owners.get(running)?.token) {
        unlinkSync(`${resolve(running.sessionFile)}.owner.json`);
      }
    } catch {
      // Unknown/busy ownership remains fail-closed; a later launch can probe exit.
    } finally {
      unlock?.();
    }
  }

  private async complete(
    running: RunningSubagent,
    policy: ResultPolicy,
    moduleSignal: AbortSignal,
  ): Promise<void> {
    let result: SubagentResult;
    const signal = running.abortController!.signal;
    try {
      const exit = await pollForExit(running.surface, AbortSignal.any([signal, moduleSignal]), {
        interval: 1000,
        sessionFile: running.sessionFile,
        sentinelFile: running.sentinelFile,
        onTick: () => {
          // A terminal read already in flight can finish after disposal.
          if (!moduleSignal.aborted && !signal.aborted) this.hooks.tick(running);
        },
      });
      result = this.extractResult(running, policy, exit);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      result = {
        name: running.name,
        task: running.task,
        summary: signal.aborted ? "Subagent cancelled." : `Subagent error: ${message}`,
        exitCode: 1,
        elapsed: Math.floor((Date.now() - running.startTime) / 1000),
        error: signal.aborted ? "cancelled" : message,
        ...(signal.aborted ? { sessionFile: running.sessionFile } : {}),
      };
    } finally {
      if (moduleSignal.aborted) {
        // Disposal owns the watcher, not the child process. Leave its pane
        // alone; a replacement runtime must not receive this run's result.
        if (this.running.get(running.id) === running) this.running.delete(running.id);
      } else {
        this.release(running);
      }
    }
    // An obsolete runtime must never wake the replacement session after reload.
    if (moduleSignal.aborted) return;
    try {
      this.hooks.refresh(false);
      this.hooks.sendMessage(
        {
          customType: "subagent_result",
          content: this.hooks.present(result, running.name),
          display: true,
          details:
            policy.kind === "resume"
              ? {
                  name: running.name,
                  task: running.task,
                  exitCode: result.exitCode,
                  elapsed: result.elapsed,
                  sessionFile: running.sessionFile,
                  sessionId: policy.sessionId,
                  ...(result.errorMessage ? { errorMessage: result.errorMessage } : {}),
                }
              : {
                  name: running.name,
                  task: running.task,
                  agent: running.agent,
                  exitCode: result.exitCode,
                  elapsed: result.elapsed,
                  sessionFile: result.sessionFile,
                  ...(result.sessionId ? { sessionId: result.sessionId } : {}),
                  ...(result.errorMessage ? { errorMessage: result.errorMessage } : {}),
                  ...(result.claudeSessionId ? { claudeSessionId: result.claudeSessionId } : {}),
                  ...(result.stats ? { stats: result.stats } : {}),
                },
        },
        { triggerTurn: true, deliverAs: "steer" },
      );
    } catch (error) {
      // Presentation/delivery errors still report through the same registered
      // message seam. A failed error delivery must not reject an unowned promise.
      const message = error instanceof Error ? error.message : String(error);
      try {
        this.hooks.sendMessage(
          {
            customType: "subagent_result",
            content:
              policy.kind === "resume"
                ? `Resume error: ${message}`
                : `Sub-agent "${running.name}" error: ${message}`,
            display: true,
            details:
              policy.kind === "resume"
                ? { name: running.name, error: message }
                : {
                    name: running.name,
                    task: running.task,
                    error: message,
                  },
          },
          { triggerTurn: true, deliverAs: "steer" },
        );
      } catch {
        /* Runtime may be shutting down; resources are already released. */
      }
    }
  }

  private extractResult(
    running: RunningSubagent,
    policy: ResultPolicy,
    exit: { exitCode: number; errorMessage?: string },
  ): SubagentResult {
    const elapsed = Math.floor((Date.now() - running.startTime) / 1000);
    if (running.cli === "claude") {
      let summary = "";
      if (running.sentinelFile) {
        try {
          summary = readFileSync(running.sentinelFile, "utf8").trim();
        } catch {}
      }
      if (!summary) {
        try {
          summary = readScreen(running.surface, 200)
            .replace(/__SUBAGENT_DONE_\d+__/, "")
            .trimEnd();
        } catch {}
      }
      summary ||=
        exit.errorMessage ??
        (exit.exitCode !== 0
          ? `Claude Code exited with code ${exit.exitCode}`
          : "Claude Code exited without output");
      const sessionId = running.sentinelFile ? copyClaudeSession(running.sentinelFile) : null;
      if (running.sentinelFile) {
        for (const file of [running.sentinelFile, running.sentinelFile + ".transcript"]) {
          try {
            unlinkSync(file);
          } catch {}
        }
      }
      return {
        name: running.name,
        task: running.task,
        summary,
        exitCode: exit.exitCode,
        elapsed,
        ...(sessionId ? { claudeSessionId: sessionId } : {}),
        ...(exit.errorMessage ? { errorMessage: exit.errorMessage } : {}),
      };
    }
    const exists = existsSync(running.sessionFile);
    const entries = exists
      ? getNewEntries(running.sessionFile, policy.kind === "resume" ? policy.entryCountBefore : 0)
      : [];
    const summary =
      findLastAssistantMessage(entries) ??
      (exit.errorMessage
        ? `Subagent error: ${exit.errorMessage}`
        : policy.kind === "resume"
          ? exit.exitCode !== 0
            ? `Resumed session exited with code ${exit.exitCode}`
            : "Resumed session exited without new output"
          : exit.exitCode !== 0
            ? `Sub-agent exited with code ${exit.exitCode}`
            : "Sub-agent exited without output");
    const stats =
      policy.kind === "initial" && exists ? summarizeSessionStats(running.sessionFile) : null;
    const sessionId =
      policy.kind === "resume"
        ? policy.sessionId
        : exists
          ? getSessionId(running.sessionFile)
          : null;
    return {
      name: running.name,
      task: running.task,
      summary,
      sessionFile: running.sessionFile,
      exitCode: exit.exitCode,
      elapsed,
      ...(sessionId ? { sessionId } : {}),
      ...(exit.errorMessage ? { errorMessage: exit.errorMessage } : {}),
      ...(stats ? { stats } : {}),
    };
  }
}

function copyClaudeSession(sentinelFile: string): string | null {
  try {
    const transcriptFile = sentinelFile + ".transcript";
    if (!existsSync(transcriptFile)) return null;
    const transcriptPath = readFileSync(transcriptFile, "utf8").trim();
    if (!transcriptPath || !existsSync(transcriptPath)) return null;
    const sessionsDir = join(process.env.HOME ?? "/tmp", ".pi", "agent", "sessions", "claude-code");
    mkdirSync(sessionsDir, { recursive: true });
    const filename = transcriptPath.split("/").pop() ?? `claude-${Date.now()}.jsonl`;
    copyFileSync(transcriptPath, join(sessionsDir, filename));
    return filename;
  } catch {
    return null;
  }
}
