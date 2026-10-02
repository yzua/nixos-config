import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  rmdirSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { randomUUID } from "node:crypto";
import { dirname, join, resolve } from "node:path";
import type { SubagentActivityState } from "./activity.ts";
import { isHerdrSurface } from "./herdr.ts";
import {
  countSessionEntryLines,
  findLastAssistantMessage,
  getNewEntries,
  getSessionId,
  isSubagentLoadout,
  inspectSubagentWriterLease,
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
  readScreenAsync,
  sendLongCommand,
  shellEscape,
  muxIdentity,
  isSurfaceId,
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
  /** Registry of the parent that dispatched this writer. */
  parentArtifactDir: string;
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
  version: 2;
  /** Writer identity, unchanged when supervision is recalled. */
  token: string;
  /** Fences obsolete watchers, including ones with a terminal read in flight. */
  supervisor: string;
  sessionFile: string;
  surface: string;
  mux: string;
  run: Omit<RunningSubagent, "abortController">;
  policy: ResultPolicy;
  loadout: SubagentLoadout | null;
  delivered: boolean;
  /** A crash around dispatch is unknown, not a shell safe to steer. */
  phase: "prepared" | "dispatched";
};

/** Own a pane from creation through result delivery, regardless of session policy.
 * Callers prepare the session and sandbox; they never register or watch a run.
 * UI observation stays outside this module, but failures in it cannot leak a pane.
 */
export class ManagedRuns {
  readonly running = new Map<string, RunningSubagent>();
  private readonly owners = new WeakMap<RunningSubagent, SessionOwner>();
  private readonly createdMux = new WeakMap<RunningSubagent, string>();
  private readonly completions = new WeakMap<RunningSubagent, Promise<void>>();
  private lifecycle = new AbortController();

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
    try {
      const identity = muxIdentity();
      if (/^herdr:.+:\d+:\d+:\d+$/.test(identity)) return identity;
      if (/^\/[^,]+,\d+$/.test(identity)) {
        // TMUX's socket path + PID alone can be reused after a server restart.
        // Bind v2 ownership to the actual socket incarnation as Herdr does.
        const stat = statSync(identity.split(",")[0], { bigint: true });
        if (stat.isSocket()) return `${identity}:${stat.dev}:${stat.ino}:${stat.ctimeNs}`;
      }
    } catch {
      // Missing/uninspectable socket identity is never authority over a pane.
    }
    throw new RunOwnershipError("Cannot establish the current multiplexer incarnation.");
  }

  private writeOwner(owner: SessionOwner): void {
    const file = `${owner.sessionFile}.owner.json`;
    const tmp = `${file}.tmp-${randomUUID()}`;
    try {
      writeFileSync(tmp, JSON.stringify(owner), { flag: "wx" });
      renameSync(tmp, file);
    } finally {
      if (existsSync(tmp)) unlinkSync(tmp);
    }
  }

  private owns(running: RunningSubagent): boolean {
    try {
      const expected = this.owners.get(running);
      const actual = this.readOwner(running.sessionFile);
      return (
        !!expected &&
        actual?.token === expected.token &&
        actual.supervisor === expected.supervisor &&
        actual.mux === this.muxIdentity()
      );
    } catch {
      return false;
    }
  }

  private readOwner(sessionFile: string): SessionOwner | undefined {
    const file = `${resolve(sessionFile)}.owner.json`;
    try {
      const owner = JSON.parse(readFileSync(file, "utf8"));
      if (
        owner.version !== 2 ||
        typeof owner.token !== "string" ||
        !owner.token ||
        owner.sessionFile !== resolve(sessionFile) ||
        typeof owner.surface !== "string" ||
        !(/^%\d+$/.test(owner.surface) || isHerdrSurface(owner.surface)) ||
        typeof owner.mux !== "string" ||
        !/^(?:herdr:.+:\d+:\d+:\d+|\/[^,]+,\d+:\d+:\d+:\d+)$/.test(owner.mux) ||
        typeof owner.supervisor !== "string" ||
        !owner.supervisor ||
        typeof owner.delivered !== "boolean" ||
        !(owner.phase === "prepared" || owner.phase === "dispatched") ||
        !owner.run ||
        Array.isArray(owner.run) ||
        owner.run.sessionFile !== owner.sessionFile ||
        owner.run.surface !== owner.surface ||
        typeof owner.run.parentArtifactDir !== "string" ||
        resolve(owner.run.parentArtifactDir) !== owner.run.parentArtifactDir ||
        typeof owner.run.id !== "string" ||
        !owner.run.id ||
        typeof owner.run.name !== "string" ||
        !owner.run.name ||
        typeof owner.run.task !== "string" ||
        !Number.isFinite(owner.run.startTime) ||
        owner.run.startTime < 0 ||
        typeof owner.run.interactive !== "boolean" ||
        !["agent", "launchScriptFile", "activityFile", "sentinelFile", "cli"].every(
          (key) => owner.run[key] === undefined || typeof owner.run[key] === "string",
        ) ||
        !(owner.run.cli === undefined || owner.run.cli === "claude") ||
        !(owner.run.cli === "claude" ? owner.run.sentinelFile : owner.run.activityFile) ||
        !owner.run.statusState ||
        Array.isArray(owner.run.statusState) ||
        owner.run.statusState.source !== (owner.run.cli === "claude" ? "claude" : "pi") ||
        owner.run.statusState.startTimeMs !== owner.run.startTime ||
        !["starting", "active", "waiting", "stalled", "running"].includes(
          owner.run.statusState.currentKind,
        ) ||
        !owner.policy ||
        !(
          owner.policy.kind === "initial" ||
          (owner.policy.kind === "resume" &&
            typeof owner.policy.sessionId === "string" &&
            !!owner.policy.sessionId &&
            Number.isInteger(owner.policy.entryCountBefore) &&
            owner.policy.entryCountBefore >= 0)
        ) ||
        !(owner.run.cli === "claude" ? owner.loadout === null : isSubagentLoadout(owner.loadout))
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

  private async claimSession(
    sessionFile: string,
    signal: AbortSignal,
    parentArtifactDir: string,
    requireExisting: boolean,
    completedLegacyRun = false,
  ): Promise<() => void> {
    // Synchronous lock acquisition precedes the first await in any launch.
    const unlock = this.lockSession(sessionFile);
    try {
      this.muxIdentity(); // Reject unknown incarnations before creating any surface.
      const owner = this.readOwner(sessionFile);
      if (!owner && requireExisting && !completedLegacyRun) {
        throw new RunOwnershipError(
          "Cannot safely resume: missing durable session ownership (legacy or unknown writer).",
        );
      }
      if (owner) {
        if (owner.run.parentArtifactDir !== resolve(parentArtifactDir)) {
          throw new RunOwnershipError("Cannot safely resume: child belongs to another parent.");
        }
        const sameMux = owner.mux === this.muxIdentity() && isSurfaceId(owner.surface);
        if (
          !sameMux &&
          inspectSubagentWriterLease(owner.sessionFile, owner.run.id, owner.token) !== "dead"
        ) {
          throw new RunOwnershipError(
            "Cannot safely resume: foreign multiplexer and writer is live or its death cannot be established.",
          );
        }
        if (sameMux) {
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
            const writer = inspectSubagentWriterLease(owner.sessionFile, owner.run.id, owner.token);
            // Losing a pane is not proof that a detached Pi process died. A
            // known-live writer also overrides stale/noisy terminal sentinels.
            if (writer === "live" || (exit.reason !== "sentinel" && writer !== "dead")) {
              throw new Error("writer is live or its death cannot be established");
            }
          } catch {
            throw new RunOwnershipError(
              "Cannot safely resume: a surviving child still owns this session, or its exit cannot be established.",
            );
          } finally {
            clearTimeout(timer);
            if (onAbort) probeSignal.removeEventListener("abort", onAbort);
          }
          if (owner.mux !== this.muxIdentity()) {
            throw new RunOwnershipError(
              "Cannot safely resume: multiplexer incarnation changed during inspection.",
            );
          }
          try {
            closeSurface(owner.surface);
          } catch {
            /* Already closed. */
          }
        }
        // Across incarnations, proof of writer death releases local metadata
        // only. Never inspect or close an ID that may now be a foreign pane.
        for (const suffix of [".exit", ".ask", ".writer.json"]) {
          const file = `${resolve(sessionFile)}${suffix}`;
          if (existsSync(file)) unlinkSync(file);
        }
        unlinkSync(`${resolve(sessionFile)}.owner.json`);
      }
      if (signal.aborted) throw new Error("Aborted while claiming subagent session");
      return unlock;
    } catch (error) {
      unlock();
      throw error;
    }
  }

  /** Recall only a handle from this parent's registry; never dispatch a writer.
   * A terminal read must establish that the same mux surface is inspectable.
   * Completion already present on that surface is delivered by the new watcher.
   */
  async recall(
    parentArtifactDir: string,
    name: string,
    sessionFile: string,
  ): Promise<RunningSubagent | undefined> {
    const signal = AbortSignal.any([this.hooks.moduleSignal(), this.lifecycle.signal]);
    const unlock = this.lockSession(sessionFile);
    let running: RunningSubagent | undefined;
    let owner: SessionOwner | undefined;
    let terminal = false;
    let adopted = false;
    try {
      owner = this.readOwner(sessionFile);
      if (!owner || owner.delivered) {
        for (const [id, run] of this.running) {
          if (run.sessionFile === resolve(sessionFile) && run.name === name)
            this.running.delete(id);
        }
        if (!owner) return undefined;
      }
      if (owner.run.parentArtifactDir !== resolve(parentArtifactDir) || owner.run.name !== name) {
        throw new RunOwnershipError("Cannot safely recall: foreign parent ownership.");
      }
      if (owner.mux !== this.muxIdentity() || !isSurfaceId(owner.surface)) {
        if (inspectSubagentWriterLease(owner.sessionFile, owner.run.id, owner.token) !== "dead") {
          throw new RunOwnershipError(
            "Cannot safely recall: foreign multiplexer and writer is live or unknown.",
          );
        }
        for (const [id, run] of this.running) {
          if (run.sessionFile === resolve(sessionFile) && run.name === name)
            this.running.delete(id);
        }
        return undefined; // A proven-dead writer can be resumed, not reattached.
      }
      if (owner.delivered) return undefined;
      if (owner.phase !== "dispatched") {
        throw new RunOwnershipError(
          "Cannot safely recall: child dispatch is incomplete or unknown.",
        );
      }
      const current = this.running.get(owner.run.id);
      if (signal.aborted) throw new RunOwnershipError("Cannot recall from a disposed runtime.");
      let readTimer: ReturnType<typeof setTimeout> | undefined;
      try {
        const screen = await Promise.race([
          readScreenAsync(owner.surface, 5),
          new Promise<never>((_resolve, reject) => {
            readTimer = setTimeout(() => reject(new Error("Ownership read timed out")), 2600);
          }),
        ]);
        terminal =
          /__SUBAGENT_DONE_\d+__/.test(screen) ||
          (owner.run.cli === "claude" &&
            !!owner.run.sentinelFile &&
            existsSync(owner.run.sentinelFile));
      } catch {
        if (inspectSubagentWriterLease(owner.sessionFile, owner.run.id, owner.token) === "dead") {
          this.running.delete(owner.run.id);
          return undefined; // Guarded resume can replace a proven-dead writer.
        }
        throw new RunOwnershipError(
          "Cannot safely recall: owned surface is missing or cannot be inspected.",
        );
      } finally {
        clearTimeout(readTimer);
      }
      if (owner.mux !== this.muxIdentity()) {
        throw new RunOwnershipError(
          "Cannot safely recall: multiplexer incarnation changed during inspection.",
        );
      }
      terminal ||=
        inspectSubagentWriterLease(owner.sessionFile, owner.run.id, owner.token) === "dead";
      if (current && this.owns(current)) {
        running = current;
      } else {
        running = { ...owner.run, abortController: new AbortController() };
        owner = { ...owner, supervisor: randomUUID() };
        this.writeOwner(owner);
        this.owners.set(running, owner);
        this.running.set(running.id, running);
        adopted = true;
      }
    } finally {
      unlock();
    }
    if (adopted) {
      this.watch(running!, owner!.policy, signal);
      try {
        this.hooks.refresh(true);
      } catch {
        // UI observation cannot abandon the recalled writer's supervision.
      }
    }
    // A completed command has returned to its shell. Never type a follow-up
    // into that shell: settle the original watcher, then let the caller resume.
    if (terminal) {
      await this.completions.get(running!);
      return undefined;
    }
    return running;
  }

  private watch(running: RunningSubagent, policy: ResultPolicy, signal: AbortSignal): void {
    this.completions.set(running, this.complete(running, policy, signal));
  }

  /** Dispose supervision without surrendering a child's durable writer claim. */
  dispose(): void {
    this.lifecycle.abort();
    this.lifecycle = new AbortController();
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
    policy:
      | { kind: "initial" }
      | { kind: "resume"; sessionId: string; completedLegacyRun?: boolean },
    prepare: (running: RunningSubagent) => LaunchPlan,
    register?: ((running: RunningSubagent) => void) | ((running: RunningSubagent) => () => void),
  ): Promise<RunningSubagent> {
    // Capture this runtime's signal, not whatever a later session installs.
    const moduleSignal = AbortSignal.any([this.hooks.moduleSignal(), this.lifecycle.signal]);
    const unlock = await this.claimSession(
      candidate.sessionFile,
      moduleSignal,
      candidate.parentArtifactDir,
      policy.kind === "resume",
      policy.kind === "resume" && policy.completedLegacyRun === true,
    );
    let running: RunningSubagent | undefined;
    let resultPolicy: ResultPolicy;
    let rollbackRegistration: (() => void) | undefined;
    try {
      // Sample only after the previous writer has truly exited: any final
      // detached output is old history, never this follow-up's summary.
      resultPolicy =
        policy.kind === "resume"
          ? { ...policy, entryCountBefore: countSessionEntryLines(candidate.sessionFile) }
          : policy;
      const incarnation = this.muxIdentity();
      const surface = createSurface(candidate.name);
      running = {
        ...candidate,
        sessionFile: resolve(candidate.sessionFile),
        parentArtifactDir: resolve(candidate.parentArtifactDir),
        surface,
        abortController: new AbortController(),
      };
      this.createdMux.set(running, incarnation);
      if (incarnation !== this.muxIdentity()) {
        throw new RunOwnershipError("Cannot prepare: multiplexer incarnation changed.");
      }
      const plan = prepare(running);
      if (incarnation !== this.muxIdentity()) {
        throw new RunOwnershipError("Cannot prepare: multiplexer incarnation changed.");
      }
      running.launchScriptFile = plan.launchScriptFile;
      const { abortController: _abort, ...run } = running;
      const owner: SessionOwner = {
        version: 2,
        token: randomUUID(),
        supervisor: randomUUID(),
        sessionFile: running.sessionFile,
        surface,
        mux: this.muxIdentity(),
        run,
        policy: resultPolicy,
        loadout: plan.kind === "pi" ? plan.loadout : null,
        delivered: false,
        phase: "prepared",
      };
      this.owners.set(running, owner);
      // Persist the pane BEFORE dispatch: even parent death cannot hide a writer.
      writeFileSync(`${owner.sessionFile}.owner.json`, JSON.stringify(owner), { flag: "wx" });
      // Retain protocol provenance even if ownership is later missing/corrupt;
      // old completed-run migration must never excuse a missing modern claim.
      const marker = `${owner.sessionFile}.owner-v2`;
      if (!existsSync(marker)) writeFileSync(marker, "2\n", { flag: "wx" });
      // The registry must survive parent death immediately after dispatch too.
      const registered = register?.(running);
      if (typeof registered === "function") rollbackRegistration = registered;
      await new Promise<void>((resolve) => setTimeout(resolve, this.hooks.shellReadyDelayMs()));
      if (moduleSignal.aborted) throw new Error("Aborted while launching subagent");
      if (!this.owns(running))
        throw new RunOwnershipError("Cannot dispatch: subagent ownership changed.");
      const command = plan.kind === "pi" ? this.piCommand(running, plan) : plan.command;
      sendLongCommand(surface, `${command}; echo '__SUBAGENT_DONE_'$?'__'`, {
        scriptPath: plan.launchScriptFile,
        scriptPreamble: plan.scriptPreamble,
      });
      owner.phase = "dispatched";
      this.writeOwner(owner);
      this.running.set(running.id, running);
      this.hooks.refresh(true);
    } catch (error) {
      if (running && this.release(running, true)) rollbackRegistration?.();
      throw error;
    } finally {
      unlock();
    }
    // The tool's signal ends with its acknowledgement. Supervision instead
    // belongs to this run and the extension runtime (shutdown or /reload).
    this.watch(running, resultPolicy, moduleSignal);
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
      PI_SUBAGENT_WRITER_TOKEN: this.owners.get(running)?.token,
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

  private release(running: RunningSubagent, lockHeld = false): boolean {
    let unlock: (() => void) | undefined;
    try {
      if (!lockHeld) unlock = this.lockSession(running.sessionFile);
      // Check BEFORE closing, not just before unlinking. Surface IDs can be reused.
      if (
        this.owners.has(running)
          ? !this.owns(running)
          : !lockHeld || this.createdMux.get(running) !== this.muxIdentity()
      )
        return false;
      closeSurface(running.surface);
      if (this.owners.has(running)) {
        // Closed failed launches remain known-safe handles too. Missing claims
        // cannot distinguish a finished legacy run from an unknown live writer.
        this.writeOwner({ ...this.readOwner(running.sessionFile)!, delivered: true });
      }
      return true;
    } catch {
      // Failed close retains the writer claim; later launch must establish exit.
      return false;
    } finally {
      if (this.running.get(running.id) === running) this.running.delete(running.id);
      unlock?.();
    }
  }

  private async finish(running: RunningSubagent, signal: AbortSignal): Promise<boolean> {
    // Recall can hold the lock across an asynchronous screen read. Contention
    // must not abandon an otherwise valid watcher's undelivered completion.
    let unlock: (() => void) | undefined;
    while (!signal.aborted && this.owns(running)) {
      try {
        unlock = this.lockSession(running.sessionFile);
        break;
      } catch {
        await new Promise<void>((resolve) => setTimeout(resolve, 25));
      }
    }
    if (!unlock) {
      if (this.running.get(running.id) === running) this.running.delete(running.id);
      return false;
    }
    try {
      if (!this.owns(running)) return false;
      const owner = this.readOwner(running.sessionFile)!;
      if (owner.delivered) return false;
      // Durable at-most-once reservation precedes the synchronous delivery seam.
      // A crash between reservation and send can lose a notification, never replay it.
      this.writeOwner({ ...owner, delivered: true });
      try {
        closeSurface(running.surface);
      } catch {
        // Keep the tombstone AND writer claim; a follow-up still probes actual exit.
      }
      return true;
    } catch {
      return false;
    } finally {
      if (this.running.get(running.id) === running) this.running.delete(running.id);
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
          if (moduleSignal.aborted || signal.aborted) return;
          if (!this.owns(running)) {
            running.abortController!.abort();
            return;
          }
          this.hooks.tick(running);
        },
      });
      if (moduleSignal.aborted || !this.owns(running)) return;
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
      if (moduleSignal.aborted || !this.owns(running)) {
        // Disposal owns the watcher, not the child process. Leave its pane
        // alone; a replacement runtime must not receive this run's result.
        if (this.running.get(running.id) === running) this.running.delete(running.id);
      }
    }
    // Fence cleanup and delivery together under the same cross-process lock.
    if (moduleSignal.aborted || !(await this.finish(running, moduleSignal))) return;
    let content: string;
    try {
      content = this.hooks.present(result, running.name);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      content =
        policy.kind === "resume"
          ? `Resume error: ${message}`
          : `Sub-agent "${running.name}" error: ${message}`;
    }
    if (moduleSignal.aborted) return;
    try {
      try {
        this.hooks.refresh(false);
      } catch {
        // UI observation must not swallow the actual result delivery.
      }
      this.hooks.sendMessage(
        {
          customType: "subagent_result",
          content,
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
    } catch {
      // A send may have enqueued before throwing. Retrying would risk a second
      // result/wakeup. The durable delivery reservation remains at-most-once.
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
    const agentDir =
      process.env.PI_CODING_AGENT_DIR ??
      (process.env.HOME ? join(process.env.HOME, ".pi", "agent") : undefined);
    if (!agentDir) return null;
    const sessionsDir = join(agentDir, "sessions", "claude-code");
    mkdirSync(sessionsDir, { recursive: true });
    const filename = transcriptPath.split("/").pop() ?? `claude-${Date.now()}.jsonl`;
    copyFileSync(transcriptPath, join(sessionsDir, filename));
    return filename;
  } catch {
    return null;
  }
}
