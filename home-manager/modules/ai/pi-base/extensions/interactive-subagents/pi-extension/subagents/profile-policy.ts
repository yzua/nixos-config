// Preserve explicit-load parent policy and worker history across launches and resumes.
import { isAbsolute } from "node:path";

export interface ProfilePolicy {
  profile: "pi-base" | "pi-home" | "pi-re";
  pi: string;
  agentDir: string;
  sessions: string;
  instructions: string[];
  skills: string[];
  extensions: string[];
}

export function isProfilePolicy(value: unknown): value is ProfilePolicy {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const v = value as Record<string, unknown>;
  const path = (value: unknown) => typeof value === "string" && isAbsolute(value);
  return (
    typeof v.profile === "string" &&
    ["pi-base", "pi-home", "pi-re"].includes(v.profile) &&
    [v.pi, v.agentDir, v.sessions].every(path) &&
    [v.instructions, v.skills, v.extensions].every(
      (values) => Array.isArray(values) && values.every(path),
    )
  );
}

export function currentProfilePolicy(): ProfilePolicy | null {
  const raw = process.env.PI_BASE_CHILD_POLICY;
  if (!raw) {
    if (["pi-base", "pi-home", "pi-re"].includes(process.env.PI_PROFILE ?? "")) {
      throw new Error("Explicit-load profile is missing its shared subagent policy");
    }
    return null; // Historical coding roles keep native behavior.
  }
  const policy = JSON.parse(raw);
  if (!isProfilePolicy(policy)) throw new Error("Invalid shared subagent profile policy");
  return policy;
}

export const COMMON_CHILD_TOOLS = [
  "read",
  "bash",
  "edit",
  "write",
  "grep",
  "find",
  "ls",
  "ask_user_question",
  "web_search",
  "web_fetch",
  "subagent",
  "subagent_message",
  "subagents_list",
  "ask_question",
];
export const COMMON_EXTENSION_TOOLS = new Set([
  "ask_user_question",
  "web_search",
  "web_fetch",
  "subagent",
  "subagent_message",
  "subagents_list",
]);
