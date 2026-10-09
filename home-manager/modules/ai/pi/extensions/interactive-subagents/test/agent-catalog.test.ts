/** Catalog tests use real private directories, never ambient cwd/config. */
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { AgentCatalog, type AgentCatalogPaths } from "../pi-extension/subagents/agent-catalog.ts";

function fixture(
  run: (
    paths: AgentCatalogPaths,
    put: (source: keyof AgentCatalogPaths, file: string, fields: string, body?: string) => void,
  ) => void,
) {
  const root = mkdtempSync(join(tmpdir(), "pi-catalog-"));
  const paths = {
    package: join(root, "package"),
    global: join(root, "global"),
    project: join(root, "project"),
  };
  const put = (
    source: keyof AgentCatalogPaths,
    file: string,
    fields: string,
    body = "IDENTITY",
  ) => {
    mkdirSync(paths[source], { recursive: true });
    writeFileSync(join(paths[source], file), `---\n${fields}\n---\n\n${body}\n`);
  };
  try {
    run(paths, put);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

test("declared-name discovery, filename loading, precedence and hidden shadowing", () =>
  fixture((paths, put) => {
    const catalog = new AgentCatalog(() => paths);
    assert.deepEqual(catalog.listVisible(), []);
    assert.equal(catalog.loadProfile("missing"), null);
    put("package", "worker.md", "name: worker\nmodel: package");
    put("global", "worker.md", "name: worker\nmodel: global");
    assert.equal(catalog.loadProfile("worker")?.model, "global");
    assert.equal(catalog.listVisible()[0].source, "global");
    put("project", "worker.md", "name: worker\nmodel: project\ndisable-model-invocation: TRUE");
    assert.deepEqual(catalog.listVisible(), []);
    assert.deepEqual(catalog.permittedNames(), { names: ["worker"], restricted: false });
    assert.equal(catalog.loadProfile("worker")?.model, "project");
    put("project", "alias.md", "name: declared\nmodel: alias");
    assert.deepEqual(
      catalog.listVisible().map((a) => [a.name, a.source]),
      [["declared", "project"]],
    );
    assert.deepEqual(catalog.permittedNames(), {
      names: ["worker", "declared"],
      restricted: false,
    });
    assert.equal(catalog.loadProfile("declared"), null);
    assert.equal(catalog.loadProfile("alias")?.name, "declared");
  }));

test("permissions are pinned, visibility is filtered, direct loading is unrestricted", () =>
  fixture((paths, put) => {
    put("package", "shown.md", "name: shown");
    put("package", "hidden.md", "name: hidden\ndisable-model-invocation: true");
    put("project", "other.md", "name: other");
    const catalog = new AgentCatalog(() => paths, " hidden, absent, shown,hidden, , ");
    assert.deepEqual(catalog.permittedNames(), {
      names: ["hidden", "absent", "shown"],
      restricted: true,
    });
    assert.deepEqual(
      catalog.listVisible().map((a) => a.name),
      ["shown"],
    );
    assert.equal(catalog.loadProfile("other")?.name, "other");
    assert.equal(catalog.loadProfile("hidden")?.disableModelInvocation, true);
    put("project", "late.md", "name: late");
    assert.deepEqual(catalog.permittedNames(), {
      names: ["hidden", "absent", "shown"],
      restricted: true,
    });
    assert.ok(new AgentCatalog(() => paths, " , ").permittedNames().names.includes("late"));
  }));

test("call-time paths and file changes are not cached; malformed overrides fall through", () =>
  fixture((paths, put) => {
    put("package", "worker.md", "model: package");
    put("project", "worker.md", "model: project");
    let current = paths;
    const catalog = new AgentCatalog(() => current);
    assert.equal(catalog.loadProfile("worker")?.model, "project");
    current = { ...paths, project: join(paths.project, "absent"), global: paths.project };
    assert.equal(catalog.listVisible()[0].source, "global");
    writeFileSync(join(paths.project, "worker.md"), "no frontmatter\n");
    assert.equal(catalog.loadProfile("worker")?.model, "package");
    assert.equal(catalog.listVisible()[0].source, "package");
    put("package", "ignored.MD", "name: ignored");
    put("package", "ignored.txt", "name: ignored");
    assert.deepEqual(catalog.permittedNames(), { names: ["worker"], restricted: false });
  }));

test("frontmatter retains narrow parsing, field defaults and all loadout fields", () =>
  fixture((paths, put) => {
    put(
      "project",
      "profile.md",
      [
        "description: test",
        "model: provider/model",
        "tools: read, bash",
        "skill: preferred",
        "skills: ignored",
        "thinking: high",
        "subagent_agents: scout, researcher, ,scout",
        "auto-exit: true",
        "interactive: True",
        "session-mode: lineage-only",
        "system-prompt: replace",
        "cwd: relative/path",
        "cli: claude",
      ].join("\n"),
      "  IDENTITY  ",
    );
    const catalog = new AgentCatalog(() => paths);
    assert.deepEqual(catalog.loadProfile("profile"), {
      name: "profile",
      description: "test",
      model: "provider/model",
      tools: "read, bash",
      skills: "preferred",
      thinking: "high",
      subagentAgents: ["scout", "researcher", "scout"],
      autoExit: true,
      interactive: false,
      sessionMode: "lineage-only",
      systemPromptMode: "replace",
      cwd: "relative/path",
      cli: "claude",
      body: "IDENTITY",
      disableModelInvocation: false,
    });
    for (const mode of ["standalone", "fork", "sideways"]) {
      put(
        "project",
        "profile.md",
        `session-mode: ${mode}\nsystem-prompt: invalid\nsubagent_agents: ,\nauto-exit: false`,
        "",
      );
      const loaded = catalog.loadProfile("profile")!;
      assert.equal(loaded.sessionMode, mode === "sideways" ? undefined : mode);
      assert.equal(loaded.systemPromptMode, undefined);
      assert.equal(loaded.interactive, undefined);
      assert.equal(loaded.autoExit, false);
      assert.equal(loaded.subagentAgents, undefined);
      assert.equal(loaded.body, undefined);
    }
    put(
      "project",
      "profile.md",
      "skills: fallback\ninteractive: true\ndisable-model-invocation: false",
    );
    assert.equal(catalog.loadProfile("profile")?.skills, "fallback");
    assert.equal(catalog.loadProfile("profile")?.interactive, true);
    writeFileSync(join(paths.project, "profile.md"), "---\r\nname: CRLF\r\n---\r\nBODY");
    assert.equal(catalog.loadProfile("profile"), null);
  }));
