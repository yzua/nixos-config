import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import type { AgentDefaults } from "./child-launch.ts";

type AgentSource = "package" | "global" | "project";
export interface AgentDefinition extends AgentDefaults {
  name: string;
  description?: string;
  disableModelInvocation: boolean;
}
export interface ListedAgentDefinition extends AgentDefinition {
  source: AgentSource;
}
export interface AgentCatalogPaths {
  package: string;
  global: string;
  project: string;
}

function value(frontmatter: string, key: string): string | undefined {
  const match = frontmatter.match(new RegExp(`^${key}:\\s*(.+)$`, "m"));
  return match ? match[1].trim() : undefined;
}
function optionalBoolean(raw: string | undefined): boolean | undefined {
  return raw != null ? raw === "true" : undefined;
}
function commaList(raw: string | undefined): string[] | undefined {
  if (raw == null) return undefined;
  const list = raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return list.length > 0 ? list : undefined;
}
function parse(content: string, fallbackName: string): AgentDefinition | null {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return null;
  const frontmatter = match[1];
  const body = content.replace(/^---\n[\s\S]*?\n---\n*/, "").trim();
  const promptMode = value(frontmatter, "system-prompt");
  const sessionMode = value(frontmatter, "session-mode");
  return {
    name: value(frontmatter, "name") ?? fallbackName,
    description: value(frontmatter, "description"),
    model: value(frontmatter, "model"),
    tools: value(frontmatter, "tools"),
    systemPromptMode: promptMode === "replace" || promptMode === "append" ? promptMode : undefined,
    skills: value(frontmatter, "skill") ?? value(frontmatter, "skills"),
    thinking: value(frontmatter, "thinking"),
    subagentAgents: commaList(value(frontmatter, "subagent_agents")),
    autoExit: optionalBoolean(value(frontmatter, "auto-exit")),
    interactive: optionalBoolean(value(frontmatter, "interactive")),
    sessionMode:
      sessionMode === "standalone" || sessionMode === "lineage-only" || sessionMode === "fork"
        ? sessionMode
        : undefined,
    cwd: value(frontmatter, "cwd"),
    cli: value(frontmatter, "cli"),
    body: body || undefined,
    disableModelInvocation:
      value(frontmatter, "disable-model-invocation")?.toLowerCase() === "true",
  };
}

/** Profile policy with explicitly supplied paths (resolved afresh for each call).
 * The allowlist is pinned at construction; paths and file contents are not.
 * Discovery uses declared names, but direct loading deliberately uses filenames
 * and neither permission nor visibility filters it. Hidden overrides still
 * shadow lower-precedence definitions and participate in permission discovery.
 */
export class AgentCatalog {
  private readonly allowlist: Set<string> | null;

  constructor(
    private readonly paths: () => AgentCatalogPaths,
    allowed?: string,
  ) {
    const list = commaList(allowed);
    this.allowlist = list ? new Set(list) : null;
  }

  listVisible(): ListedAgentDefinition[] {
    return this.discover().filter((agent) => !agent.disableModelInvocation);
  }

  permittedNames(): { names: string[]; restricted: boolean } {
    // A pinned grant can include names not currently present on disk. The
    // restriction fact lets callers preserve refusal wording without parsing it.
    return {
      names: this.allowlist ? [...this.allowlist] : this.discover().map((agent) => agent.name),
      restricted: this.allowlist !== null,
    };
  }

  loadProfile(name: string): AgentDefinition | null {
    const paths = this.paths();
    for (const dir of [paths.project, paths.global, paths.package]) {
      const path = join(dir, `${name}.md`);
      if (!existsSync(path)) continue;
      const parsed = parse(readFileSync(path, "utf8"), name);
      if (parsed) return parsed;
    }
    return null;
  }

  private discover(): ListedAgentDefinition[] {
    const paths = this.paths();
    const agents = new Map<string, ListedAgentDefinition>();
    for (const source of ["package", "global", "project"] as const) {
      const dir = paths[source];
      if (!existsSync(dir)) continue;
      for (const file of readdirSync(dir).filter((entry) => entry.endsWith(".md"))) {
        const parsed = parse(readFileSync(join(dir, file), "utf8"), file.replace(/\.md$/, ""));
        if (parsed) agents.set(parsed.name, { ...parsed, source });
      }
    }
    const all = [...agents.values()];
    return this.allowlist ? all.filter((agent) => this.allowlist!.has(agent.name)) : all;
  }
}
