import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import subagents, {
  __test__,
} from "../../home-manager/modules/ai/pi-base/extensions/interactive-subagents/pi-extension/subagents/index.ts";
import { pollForExit } from "../../home-manager/modules/ai/pi-base/extensions/interactive-subagents/pi-extension/subagents/run-evidence.ts";

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, realContext) => {
    const root = process.env.PI_TEST_ROOT!;
    const results: Record<string, unknown> = {};
    // Probe processes must not inherit a random parent session's provider.
    delete process.env.PI_PROVIDER;
    try {
      if (process.env.PI_TEST_SCENARIO === "panes") {
        for (const mode of [
          "missing",
          "unavailable",
          "late-sidecar",
          "transient",
          "sentinel",
          "healthy",
          "capture-error",
        ]) {
          writeFileSync(join(root, "tmux-mode"), mode);
          const sessionFile = join(root, `${mode}.jsonl`);
          let lateTimer: ReturnType<typeof setTimeout> | undefined;
          if (mode === "late-sidecar") {
            lateTimer = setTimeout(() => {
              writeFileSync(`${sessionFile}.exit`, JSON.stringify({ type: "done" }));
            }, 70);
          }
          const controller = new AbortController();
          const abortTimer = setTimeout(
            () => controller.abort(),
            mode === "healthy" ? 120 : mode === "capture-error" ? 2300 : 4000,
          );
          try {
            const start = Date.now();
            const result = await pollForExit("%99", controller.signal, {
              interval: 20,
              sessionFile,
            });
            results[mode] = { ...result, elapsedMs: Date.now() - start };
          } catch (error) {
            results[mode] = { error: String(error) };
          } finally {
            clearTimeout(abortTimer);
            clearTimeout(lateTimer);
          }
        }
      } else {
        const tools = new Map<string, { execute: (...args: unknown[]) => Promise<any> }>();
        const handlers = new Map<string, Array<(...args: unknown[]) => unknown>>();
        const mockApi = {
          on(event: string, handler: (...args: unknown[]) => unknown) {
            handlers.set(event, [...(handlers.get(event) ?? []), handler]);
          },
          registerTool(tool: { name: string; execute: (...args: unknown[]) => Promise<any> }) {
            tools.set(tool.name, tool);
          },
          registerCommand() {},
          registerShortcut() {},
          registerMessageRenderer() {},
          sendMessage() {},
        };
        subagents(mockApi as unknown as ExtensionAPI);
        const context = {
          modelRegistry: realContext.modelRegistry,
          cwd: root,
          hasUI: false,
          sessionManager: {
            getSessionFile: () => join(root, "parent.jsonl"),
            getSessionId: () => "fixture-parent",
            getSessionDir: () => root,
          },
        };
        const run = (tool: string, args: Record<string, unknown>) =>
          tools.get(tool)!.execute("fixture", args, undefined, undefined, context);
        try {
          if (process.env.PI_TEST_SCENARIO === "provider-families") {
            writeFileSync(join(root, "tmux-mode"), "healthy");
            const models = [
              { provider: "codex-lb", id: "gpt-fixture" },
              { provider: "codex-lb", id: "gpt-other" },
              { provider: "zai", id: "glm-fixture" },
              { provider: "opencode-cli", id: "opencode/free-fixture" },
              { provider: "kilo-free", id: "kilo-auto/free" },
            ];
            const parent = {
              ...context,
              model: models[0],
              modelRegistry: { getAvailable: async () => models },
            };
            const invoke = (tool: string, args: Record<string, unknown>) =>
              tools.get(tool)!.execute("fixture", args, undefined, undefined, parent);
            const panes = () =>
              existsSync(join(root, "pane-count"))
                ? readFileSync(join(root, "pane-count"), "utf8")
                : "0";
            const profile = join(process.env.PI_CODING_AGENT_DIR!, "agents", "fixture.md");
            const setProfile = (extra = "") =>
              writeFileSync(
                profile,
                `---\nname: fixture\ntools: read\nauto-exit: true\n${extra}---\nOffline role.\n`,
              );
            const rejected: Record<string, string> = {};
            async function refuse(label: string, model?: string, cwd?: string) {
              const before = panes();
              try {
                const response = await invoke("subagent", {
                  agent: "fixture",
                  name: label,
                  task: "refuse",
                  model,
                  cwd,
                });
                rejected[label] = response.details?.error ?? "UNEXPECTED_LAUNCH";
              } catch (error) {
                rejected[label] = String(error);
              }
              if (panes() !== before) throw new Error(`${label} created a pane`);
            }
            setProfile();
            for (const active of models.filter((m) => m.id !== "gpt-other")) {
              parent.model = active;
              for (const target of models.filter((m) => m.provider !== active.provider)) {
                const free = ["opencode-cli", "kilo-free"];
                if (free.includes(active.provider) && free.includes(target.provider)) continue;
                await refuse(
                  `${active.provider}-to-${target.provider}-${target.id.replaceAll("/", "-")}`,
                  `${target.provider}/${target.id}`,
                );
              }
            }
            parent.model = models[4];
            setProfile("model: codex-lb/gpt-fixture\n");
            await refuse("profile-bypass");
            setProfile("cli: claude\nmodel: sonnet\n");
            await refuse("claude-bypass");
            setProfile();
            const role = join(root, "role");
            mkdirSync(join(role, ".pi/agent"), { recursive: true });
            await refuse("role-bypass", "codex-lb/gpt-fixture", role);
            parent.model = { provider: "empty-provider", id: "missing" };
            await refuse("empty-family", "codex-lb/gpt-fixture");
            results.rejected = rejected;
            results.panesBeforeValid = panes();
            const valid = [];
            for (const active of models.filter((m) => m.id !== "gpt-other")) {
              parent.model = active;
              const response = await invoke("subagent", {
                agent: "fixture",
                name: `${active.provider}-inherit`,
                task: "inherit",
              });
              valid.push({
                parent: active,
                details: response.details,
                command: readFileSync(response.details.launchScriptFile, "utf8"),
                loadout: JSON.parse(
                  readFileSync(`${response.details.sessionFile}.loadout.json`, "utf8"),
                ),
              });
            }
            results.inherited = valid;
            const picked = [];
            for (const [active, target] of [
              [models[0], models[1]],
              [models[3], models[4]],
              [models[4], models[3]],
            ]) {
              parent.model = active!;
              const response = await invoke("subagent", {
                agent: "fixture",
                name: "allowed-choice",
                task: "pick",
                model: `${target!.provider}/${target!.id}`,
              });
              picked.push(
                JSON.parse(readFileSync(`${response.details.sessionFile}.loadout.json`, "utf8"))
                  .model,
              );
            }
            results.picked = picked;
            parent.model = models[4];
            const listed = await invoke("subagents_list", {});
            results.listed = listed.content.map((c: any) => c.text).join("\n");
            const first = valid[0]!.details;
            const before = panes();
            results.steerRefused = (
              await invoke("subagent_message", {
                name: first.name,
                message: "must not steer codex from kilo",
              })
            ).details;
            if (panes() !== before) throw new Error("Rejected steer created a pane");
            const registryPath = join(
              root,
              "artifacts",
              "fixture-parent",
              "subagent-registry.json",
            );
            const registry = readFileSync(registryPath, "utf8");
            writeFileSync(registryPath, "{}");
            results.steerWithoutRegistryRefused = (
              await invoke("subagent_message", {
                name: first.name,
                message: "missing registry must not bypass the family",
              })
            ).details;
            writeFileSync(registryPath, registry);
            for (const running of __test__.runningSubagents.values()) {
              execFileSync("tmux", ["writer-lease", running.sessionFile]);
              running.abortController?.abort();
            }
            const deadline = Date.now() + 4000;
            while (__test__.runningSubagents.size && Date.now() < deadline)
              await new Promise((resolve) => setTimeout(resolve, 10));
            if (__test__.runningSubagents.size) throw new Error("Cancelled runs did not settle");
            writeFileSync(
              first.sessionFile,
              `${JSON.stringify({ type: "session", id: "fixture-child", version: 3, cwd: root })}\n`,
            );
            results.resumeRefused = (
              await invoke("subagent_message", {
                name: first.name,
                message: "must not resume codex from kilo",
              })
            ).details;
            if (panes() !== before) throw new Error("Rejected resume created a pane");
            parent.model = models[0];
            results.resume = (
              await invoke("subagent_message", { name: first.name, message: "same family" })
            ).details;
            const resumed = [...__test__.runningSubagents.values()].find(
              (r) => r.name === first.name,
            )!;
            results.resumeCommand = readFileSync(resumed.launchScriptFile!, "utf8");
            parent.model = models[4];
            const legacy = valid[1]!.details;
            const legacyPath = `${legacy.sessionFile}.loadout.json`;
            const snapshot = JSON.parse(readFileSync(legacyPath, "utf8"));
            snapshot.model = null;
            writeFileSync(legacyPath, JSON.stringify(snapshot));
            writeFileSync(
              legacy.sessionFile,
              `${JSON.stringify({ type: "session", id: "legacy-child", version: 3, cwd: root })}\n`,
            );
            results.legacyRefused = (
              await invoke("subagent_message", {
                name: legacy.name,
                message: "legacy must not default",
              })
            ).details;
          } else if (process.env.PI_TEST_SCENARIO === "model-guard") {
            writeFileSync(join(root, "tmux-mode"), "healthy");
            const profile = join(process.env.PI_CODING_AGENT_DIR!, "agents", "fixture.md");
            const setProfile = (model?: string, cli?: string) =>
              writeFileSync(
                profile,
                `---\nname: fixture\ntools: read\nauto-exit: true\n${model ? `model: ${model}\n` : ""}${cli ? `cli: ${cli}\n` : ""}---\nOffline role.\n`,
              );
            const refused: Record<string, unknown> = {};
            for (const [label, override, profileModel] of [
              ["override", "offline-missing", undefined],
              ["profile", undefined, "offline-missing"],
              ["unavailable", "unconfigured/offline-shared", undefined],
              ["thinking-as-model", "high", undefined],
            ]) {
              setProfile(profileModel);
              try {
                await run("subagent", {
                  agent: "fixture",
                  name: "guard",
                  task: "must not launch",
                  model: override,
                });
              } catch (error) {
                refused[label!] = String(error);
              }
            }
            results.refused = refused;
            const previousProvider = process.env.PI_PROVIDER;
            process.env.PI_PROVIDER = "configured-provider";
            try {
              try {
                await run("subagent", {
                  agent: "fixture",
                  name: "guard",
                  task: "must not launch",
                  model: "zai-like/offline-other",
                });
              } catch (error) {
                refused["cross-provider"] = String(error);
              }
            } finally {
              if (previousProvider === undefined) delete process.env.PI_PROVIDER;
              else process.env.PI_PROVIDER = previousProvider;
            }
            const scopedContext = { ...context };
            (scopedContext as any).scopedModels = [
              { model: { provider: "configured-provider", id: "offline-shared" } },
            ];
            const scopedRun = (tool: string, args: Record<string, unknown>) =>
              tools.get(tool)!.execute("fixture", args, undefined, undefined, scopedContext);
            try {
              await scopedRun("subagent", {
                agent: "fixture",
                name: "guard",
                task: "must not launch",
                model: "zai-like/offline-other",
              });
            } catch (error) {
              refused["scoped"] = String(error);
            }
            results.refused = refused;
            results.panesBeforeValid = existsSync(join(root, "pane-count"))
              ? readFileSync(join(root, "pane-count"), "utf8")
              : "0";
            results.registryBeforeValid = existsSync(
              join(root, "artifacts", "fixture-parent", "subagent-registry.json"),
            );
            results.reservations = [...__test__.reservedNames];
            const roleCwd = join(root, "role");
            const roleAgentDir = join(roleCwd, ".pi", "agent");
            mkdirSync(roleAgentDir, { recursive: true });
            writeFileSync(
              join(roleAgentDir, "models.json"),
              JSON.stringify({
                providers: {
                  "role-provider": {
                    api: "openai-responses",
                    baseUrl: "http://127.0.0.1:9",
                    apiKey: "unused-offline-test-key",
                    models: [{ id: "offline-role" }],
                  },
                },
              }),
            );
            const valid: Record<string, unknown>[] = [];
            for (const [label, override, profileModel, cli] of [
              ["qualified", "configured-provider/offline-shared", "offline-missing", undefined],
              ["unqualified", "offline-shared", undefined, undefined],
              ["profile", undefined, "offline-shared", undefined],
              ["inherit", undefined, undefined, undefined],
              ["empty-override", "", undefined, undefined],
              ["scoped", "offline-shared", undefined, undefined],
              ["role", "role-provider/offline-role", undefined, undefined],
              ["claude", "sonnet", "opus", "claude"],
              ["thinking", undefined, undefined, undefined],
            ]) {
              setProfile(profileModel, cli);
              const invoke = label === "scoped" ? scopedRun : run;
              const response = await invoke("subagent", {
                agent: "fixture",
                name: "guard",
                task: "offline task",
                model: override,
                ...(label === "thinking" ? { thinking: "high" } : {}),
                ...(label === "role" ? { cwd: roleCwd } : {}),
              });
              valid.push({
                label,
                name: response.details.name,
                command: readFileSync(response.details.launchScriptFile, "utf8"),
                loadout: cli
                  ? null
                  : JSON.parse(
                      readFileSync(`${response.details.sessionFile}.loadout.json`, "utf8"),
                    ),
              });
            }
            results.valid = valid;
          } else if (process.env.PI_TEST_SCENARIO === "launch-policy") {
            writeFileSync(join(root, "tmux-mode"), "managed-empty");
            writeFileSync(
              join(root, "parent.jsonl"),
              [
                { type: "session", id: "fixture-parent", version: 3, cwd: root },
                {
                  type: "message",
                  id: "prior-user",
                  message: { role: "user", content: [{ type: "text", text: "prior task" }] },
                },
                {
                  type: "message",
                  id: "prior-answer",
                  parentId: "prior-user",
                  message: {
                    role: "assistant",
                    content: [{ type: "text", text: "PARENT_CONTEXT" }],
                  },
                },
                {
                  type: "message",
                  id: "current-user",
                  parentId: "prior-answer",
                  message: { role: "user", content: [{ type: "text", text: "current dispatch" }] },
                },
              ]
                .map((entry) => JSON.stringify(entry))
                .join("\n") + "\n",
            );
            const launches: Record<string, unknown>[] = [];
            for (const mode of ["standalone", "lineage-only", "fork"]) {
              const agent = `policy-${mode}`;
              writeFileSync(
                join(process.env.PI_CODING_AGENT_DIR!, "agents", `${agent}.md`),
                `---\nname: ${agent}\ntools: read\nskills: review,lint\nmodel: offline-profile\nthinking: medium\nsystem-prompt: replace\nsession-mode: ${mode}\nauto-exit: true\n---\nROLE_IDENTITY`,
              );
              const spawned = await run("subagent", {
                agent,
                name: agent,
                task: "CHILD_TASK",
                model: "offline-override",
              });
              const details = spawned.details;
              const command = readFileSync(details.launchScriptFile, "utf8");
              const taskFile = command.match(/'@([^']+)'/);
              const identityFile = command.match(/--system-prompt '([^']+)'/);
              launches.push({
                mode,
                command,
                taskArtifact: taskFile ? readFileSync(taskFile[1], "utf8") : null,
                identity: identityFile ? readFileSync(identityFile[1], "utf8") : null,
                session: readFileSync(details.sessionFile, "utf8"),
                loadout: JSON.parse(readFileSync(`${details.sessionFile}.loadout.json`, "utf8")),
              });
            }
            results.launches = launches;
          } else if (process.env.PI_TEST_SCENARIO === "launch-failure") {
            writeFileSync(join(root, "tmux-mode"), "send-failure");
            try {
              await run("subagent", { agent: "fixture", name: "retryable", task: "fail" });
            } catch (error) {
              results.launchError = String(error);
            }
            writeFileSync(join(root, "tmux-mode"), "sentinel");
            results.retry = (
              await run("subagent", {
                agent: "fixture",
                name: "retryable",
                task: "retry",
              })
            ).details;
            await new Promise((resolve) => setTimeout(resolve, 100));
            results.closedPanes = readFileSync(join(root, "tmux-calls"), "utf8")
              .trim()
              .split("\n")
              .map((line) => JSON.parse(line))
              .filter((args) => args[0] === "kill-pane")
              .map((args) => args[2]);
          } else {
            const trustProbe = process.env.PI_TEST_SCENARIO === "trust";
            const spawns = await Promise.all([
              run("subagent", { agent: "fixture", name: "duplicate", task: "first" }),
              run("subagent", {
                agent: "fixture",
                name: trustProbe ? "other" : "duplicate",
                task: "second",
              }),
            ]);
            results.parallel = spawns.map((spawn) => spawn.details);
            results.spawnCommands = spawns.map((spawn) =>
              readFileSync(spawn.details.launchScriptFile, "utf8"),
            );

            // A real short-lived shim writes a matching writer lease before
            // cancellation. Await completion cleanup; clearing the map alone
            // would leave unknown writer ownership, correctly refusing resume.
            for (const running of __test__.runningSubagents.values()) {
              execFileSync("tmux", ["writer-lease", running.sessionFile]);
              running.abortController?.abort();
            }
            const deadline = Date.now() + 4000;
            while (__test__.runningSubagents.size && Date.now() < deadline)
              await new Promise((resolve) => setTimeout(resolve, 10));
            if (__test__.runningSubagents.size) throw new Error("Cancelled runs did not settle");
            const first = spawns[0].details;
            writeFileSync(
              first.sessionFile,
              `${JSON.stringify({ type: "session", id: "fixture-child", version: 3, cwd: root })}\n`,
            );
            const third = await run("subagent", {
              agent: "fixture",
              name: trustProbe ? "third" : "duplicate",
              task: "third",
            });
            results.finishedName = third.details.name;
            results.registryBeforeResume = JSON.parse(
              readFileSync(
                join(root, "artifacts", "fixture-parent", "subagent-registry.json"),
                "utf8",
              ),
            );
            const resumed = await run("subagent_message", {
              name: first.name,
              message: "continue",
            });
            results.resume = resumed.details;
            const resumedRunning = [...__test__.runningSubagents.values()].find(
              (item) => item.id === resumed.details.id,
            );
            results.resumeCommand = resumedRunning?.launchScriptFile
              ? readFileSync(resumedRunning.launchScriptFile, "utf8")
              : undefined;
            results.reservations = [...__test__.reservedNames];
            results.loadoutExists = existsSync(`${first.sessionFile}.loadout.json`);
          }
        } finally {
          for (const handler of handlers.get("session_shutdown") ?? []) await handler({}, context);
          await new Promise((resolve) => setTimeout(resolve, 50));
        }
      }
    } catch (error) {
      results.failure = String(error);
    } finally {
      writeFileSync(join(root, "results.json"), JSON.stringify(results));
      realContext.shutdown();
    }
  });
}
