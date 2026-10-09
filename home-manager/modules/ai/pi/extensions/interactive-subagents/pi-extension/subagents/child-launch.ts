import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { shellEscape } from "./tmux.ts";
import { writeSubagentLoadout, type SubagentLoadout } from "./session.ts";
import type { LaunchPlan, RunningSubagent } from "./managed-run.ts";

export interface AgentDefaults {
  model?: string;
  tools?: string;
  skills?: string;
  thinking?: string;
  /** Presence grants spawning, constrained by PI_SUBAGENT_ALLOWED. */
  subagentAgents?: string[];
  autoExit?: boolean;
  interactive?: boolean;
  systemPromptMode?: "append" | "replace";
  sessionMode?: "standalone" | "lineage-only" | "fork";
  cwd?: string;
  cli?: string;
  body?: string;
  disableModelInvocation?: boolean;
}

type LaunchRequest =
  | {
      kind: "initial";
      profile: AgentDefaults | null;
      model?: string;
      cwd: string | null;
      agentDir: string | null;
    }
  | { kind: "resume"; loadout: SubagentLoadout };

/** Shared with tool-extension registration so grants and backing paths agree. */
export const SPAWNING_TOOLS = ["subagent", "subagent_message", "subagents_list"] as const;

function toolAllowlist(tools: string | undefined, spawnable: string[] | undefined): string | null {
  const requested = (tools ?? "")
    .split(",")
    .map((tool) => tool.trim())
    .filter(Boolean);
  const grantSpawning = !!spawnable?.length;
  if (!requested.length && !grantSpawning) return null;
  const allow = new Set(requested);
  if (grantSpawning) for (const tool of SPAWNING_TOOLS) allow.add(tool);
  allow.add("ask_question");
  return [...allow].join(",");
}

function safeName(name: string, fallback: string): string {
  return (
    name
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, "")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "") || fallback
  );
}

function timestamp(): string {
  return new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
}

function writeArtifact(file: string, content: string): string {
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, content, "utf8");
  return file;
}

/** Prepare initial and resumed commands behind one sandbox/handoff interface.
 * The caller supplies resolved profile/path facts, never assembles CLI policy.
 * ManagedRuns invokes this only after claiming the session; it still owns
 * registration, writer fencing, dispatch and supervision.
 */
export class ChildLaunch {
  constructor(
    private readonly subagentsDir: string,
    private readonly toolExtensionPath: (tool: string) => string | undefined,
  ) {}

  prepare(request: LaunchRequest, running: RunningSubagent): LaunchPlan {
    if (request.kind === "initial" && request.profile?.cli === "claude") {
      return this.claude(request, running);
    }
    return this.pi(request, running);
  }

  private claude(
    request: Extract<LaunchRequest, { kind: "initial" }>,
    running: RunningSubagent,
  ): LaunchPlan {
    const parts = [
      `PI_CLAUDE_SENTINEL=${shellEscape(running.sentinelFile!)}`,
      "claude",
      "--dangerously-skip-permissions",
    ];
    const plugin = join(this.subagentsDir, "plugin");
    if (existsSync(plugin)) parts.push("--plugin-dir", shellEscape(plugin));
    const model = request.model ?? request.profile?.model;
    if (model) parts.push("--model", shellEscape(model));
    if (request.profile?.body)
      parts.push("--append-system-prompt", shellEscape(request.profile.body));
    // Claude always receives the caller's task directly, not Pi's wrapper.
    parts.push(shellEscape(running.task));
    return {
      kind: "command",
      command: `${request.cwd ? `cd ${shellEscape(request.cwd)} && ` : ""}${parts.join(" ")}`,
      launchScriptFile: join(
        running.parentArtifactDir,
        "subagent-scripts",
        `${safeName(running.name, "subagent")}-${running.id}.sh`,
      ),
      scriptPreamble: [
        `# Claude Code subagent launch script for ${running.name}`,
        `# Generated: ${new Date().toISOString()}`,
        `# Surface: ${running.surface}`,
      ].join("\n"),
    };
  }

  private sandbox(parts: string[], loadout: SubagentLoadout, running: RunningSubagent): void {
    if (loadout.model) parts.push("--model", shellEscape(loadout.model));
    if (loadout.thinking) parts.push("--thinking", shellEscape(loadout.thinking));
    if (loadout.identity) {
      const flag =
        loadout.systemPromptMode === "replace" ? "--system-prompt" : "--append-system-prompt";
      const file = writeArtifact(
        join(
          running.parentArtifactDir,
          `context/${safeName(running.name, "subagent")}-sysprompt-${timestamp()}.md`,
        ),
        loadout.identity,
      );
      parts.push(flag, shellEscape(file));
    }
    // A null allowlist deliberately preserves unrestricted launches/resumes.
    if (loadout.toolAllowlist) {
      parts.push("--no-extensions", "--tools", shellEscape(loadout.toolAllowlist));
      const extensions = new Set<string>();
      for (const tool of loadout.toolAllowlist.split(",")) {
        const file = this.toolExtensionPath(tool);
        if (file && existsSync(file)) extensions.add(file);
      }
      for (const file of extensions) parts.push("-e", shellEscape(file));
    }
  }

  private pi(request: LaunchRequest, running: RunningSubagent): LaunchPlan {
    const profile = request.kind === "initial" ? request.profile : null;
    const identity = profile?.body ?? null;
    const identityInSystemPrompt = profile?.systemPromptMode && identity;
    const loadout: SubagentLoadout =
      request.kind === "resume"
        ? request.loadout
        : {
            agent: running.agent ?? null,
            toolAllowlist: toolAllowlist(profile?.tools, profile?.subagentAgents),
            model: request.model ?? profile?.model ?? null,
            thinking: profile?.thinking ?? null,
            systemPromptMode: profile?.systemPromptMode ?? null,
            identity: identityInSystemPrompt ? identity : null,
            spawnable: profile?.subagentAgents ?? null,
            autoExit: profile?.autoExit ?? false,
            cwd: request.cwd,
            agentDir: request.agentDir,
          };
    if (request.kind === "initial") writeSubagentLoadout(running.sessionFile, loadout);
    const parts = [
      "pi",
      "--approve",
      "--session",
      shellEscape(running.sessionFile),
      "-e",
      shellEscape(join(this.subagentsDir, "subagent-done.ts")),
    ];
    this.sandbox(parts, loadout, running);

    let resumeMsgFile: string | undefined;
    if (request.kind === "resume") {
      if (running.task) {
        resumeMsgFile = writeArtifact(
          join(
            running.parentArtifactDir,
            "subagent-resume",
            `${safeName(running.name, "resume")}-${timestamp()}.md`,
          ),
          running.task,
        );
        parts.push(shellEscape(`@${resumeMsgFile}`));
      }
    } else {
      const direct = profile?.sessionMode === "fork";
      const modeHint = profile?.autoExit
        ? "Complete your task autonomously. When you are finished, simply stop — your session ends automatically."
        : "Complete your task. The user can interact with you at any time, and the session ends when the user exits the pane.";
      const summaryInstruction = profile?.autoExit
        ? "Your FINAL assistant message should summarize what you accomplished."
        : "Your FINAL assistant message (before the user exits) should summarize what you accomplished.";
      const roleBlock = identity && !identityInSystemPrompt ? `\n\n${identity}` : "";
      const fullTask = direct
        ? running.task
        : `${roleBlock}\n\n${modeHint}\n\n${running.task}\n\n${summaryInstruction}`;
      const taskArg = direct
        ? fullTask
        : `@${writeArtifact(
            join(
              running.parentArtifactDir,
              `context/${safeName(running.name, "subagent")}-${timestamp()}.md`,
            ),
            fullTask,
          )}`;
      const skills = (profile?.skills ?? "")
        .split(",")
        .map((skill) => skill.trim())
        .filter(Boolean)
        .map((skill) => `/skill:${skill}`);
      // Pi concatenates @file with messages[0]. Keep /skill: in separate
      // follow-ups for blank sessions so the child's skill expansion works.
      for (const arg of [...(!direct && skills.length ? [""] : []), ...skills, taskArg]) {
        parts.push(shellEscape(arg));
      }
    }
    const resume = request.kind === "resume";
    return {
      kind: "pi",
      parts,
      loadout,
      // Resumes always run autonomously, independent of the saved initial policy.
      autoExit: resume || (profile?.autoExit ?? false),
      launchScriptFile: join(
        running.parentArtifactDir,
        "subagent-scripts",
        resume
          ? `${safeName(running.name, "resume")}-resume-${Date.now()}.sh`
          : `${safeName(running.name, "subagent")}-${running.id}.sh`,
      ),
      scriptPreamble: [
        `# Subagent ${resume ? "resume" : "launch"} script for ${running.name}`,
        `# Generated: ${new Date().toISOString()}`,
        `# Session: ${running.sessionFile}`,
        `# Surface: ${running.surface}`,
        ...(resumeMsgFile ? [`# Resume message file: ${resumeMsgFile}`] : []),
      ].join("\n"),
    };
  }
}
