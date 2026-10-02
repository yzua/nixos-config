import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import subagents, {
  __test__,
} from "../../home-manager/modules/ai/pi/extensions/interactive-subagents/pi-extension/subagents/index.ts";
import { pollForExit } from "../../home-manager/modules/ai/pi/extensions/interactive-subagents/pi-extension/subagents/tmux.ts";

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, realContext) => {
    const root = process.env.PI_TEST_ROOT!;
    const results: Record<string, unknown> = {};
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
          if (process.env.PI_TEST_SCENARIO === "launch-failure") {
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
