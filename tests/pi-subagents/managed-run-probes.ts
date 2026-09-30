import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import subagents, {
  __test__,
} from "../../home-manager/modules/ai/pi/extensions/interactive-subagents/pi-extension/subagents/index.ts";

// Load through installed Pi, invoke the tools it registers, and substitute only
// the external tmux command. No child CLI or paid provider is executed.
export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, realContext) => {
    const root = process.env.PI_TEST_ROOT!;
    const results: Record<string, unknown> = {};
    const tools = new Map<string, { execute: (...args: unknown[]) => Promise<any> }>();
    const handlers = new Map<string, Array<(...args: unknown[]) => unknown>>();
    const delivered: Array<Record<string, any>> = [];
    let throwDelivery = false;
    let widgetUpdates = 0;
    const api = {
      on(event: string, handler: (...args: unknown[]) => unknown) {
        handlers.set(event, [...(handlers.get(event) ?? []), handler]);
      },
      registerTool(tool: { name: string; execute: (...args: unknown[]) => Promise<any> }) {
        tools.set(tool.name, tool);
      },
      registerCommand() {},
      registerMessageRenderer() {},
      sendMessage(message: Record<string, unknown>, options: Record<string, unknown>) {
        if (message.customType !== "subagent_result") return;
        if (throwDelivery) {
          throwDelivery = false;
          throw new Error("OFFLINE_DELIVERY_FAILURE");
        }
        delivered.push({ ...message, options });
      },
    };
    const context = {
      cwd: root,
      hasUI: true,
      ui: {
        setWidget() {
          widgetUpdates++;
        },
      },
      sessionManager: {
        getSessionFile: () => join(root, "parent.jsonl"),
        getSessionId: () => "fixture-parent",
        getSessionDir: () => root,
      },
    };
    const event = async (name: string) => {
      for (const handler of handlers.get(name) ?? []) await handler({}, context);
    };
    const run = (name: string, args: Record<string, unknown>) =>
      tools.get(name)!.execute("fixture", args, undefined, undefined, context);
    const mode = (value: string) => writeFileSync(join(root, "tmux-mode"), value);
    const waitForDelivery = async (count: number) => {
      const deadline = Date.now() + 4000;
      while (delivered.length < count && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 10));
      }
      if (delivered.length !== count)
        throw new Error(`Expected ${count} results, received ${delivered.length}`);
    };
    const calls = () =>
      readFileSync(join(root, "tmux-calls"), "utf8")
        .trim()
        .split("\n")
        .map((line) => JSON.parse(line));
    const spawn = (name: string) =>
      run("subagent", { agent: "fixture", name, task: "offline task" });
    const resume = () => run("subagent_message", { name: "managed", message: "offline followup" });
    try {
      subagents(api as unknown as ExtensionAPI);
      await event("session_start");
      const scenario = process.env.PI_TEST_SCENARIO;
      if (scenario === "lifecycle") {
        const profile = join(process.env.PI_CODING_AGENT_DIR!, "agents", "fixture.md");
        writeFileSync(
          profile,
          `---\nname: fixture\ntools: read\nmodel: offline-fixed\nthinking: high\nsubagent_agents: scout\nauto-exit: false\ninteractive: true\nsystem-prompt: replace\ncwd: ${root}\n---\nFixed role.\n`,
        );
        mode("managed");
        const initial = await spawn("managed");
        await waitForDelivery(1);
        // A changed profile must not widen a persistent session's sandbox.
        writeFileSync(
          profile,
          "---\nname: fixture\ntools: read,bash,write\nmodel: changed\n---\nChanged role.\n",
        );
        const followed = await resume();
        await waitForDelivery(2);
        mode("managed-empty");
        const empty = await resume();
        await waitForDelivery(3);
        const scripts = [initial, followed, empty].map((result) =>
          readFileSync(result.details.launchScriptFile, "utf8"),
        );
        results.commands = scripts;
        results.identities = scripts.map((script) => {
          const path = script.match(/--system-prompt '([^']+)'/)![1];
          return readFileSync(path, "utf8");
        });
        unlinkSync(`${initial.details.sessionFile}.loadout.json`);
        results.panesBeforeRefusal = readFileSync(join(root, "pane-count"), "utf8");
        results.missingLoadout = (await resume()).details;
        results.refusedPanes = readFileSync(join(root, "pane-count"), "utf8");
        results.closedPanes = calls()
          .filter((args) => args[0] === "kill-pane")
          .map((args) => args[2]);
        // Persistent names cannot be reused even when their run has finished.
        mode("healthy");
        results.nextName = (await spawn("managed")).details.name;
      } else if (scenario === "disposal") {
        mode("healthy");
        await spawn("disposed");
        await event("session_shutdown");
        widgetUpdates = 0;
        await new Promise((resolve) => setTimeout(resolve, 1100));
        results.postShutdownWidgets = widgetUpdates;
        await event("session_start");
        mode("managed");
        await spawn("replacement");
        await waitForDelivery(1);
        await new Promise((resolve) => setTimeout(resolve, 50));
      } else if (scenario === "completion-errors") {
        mode("managed-error");
        await spawn("provider-error");
        await waitForDelivery(1);
        mode("managed-invalid");
        await spawn("extraction-error");
        await waitForDelivery(2);
        mode("managed");
        throwDelivery = true;
        await spawn("delivery-error");
        await waitForDelivery(3);
        mode("healthy");
        const cancel = await spawn("cancelled");
        // Legacy internal cancellation coverage: no public cancel capability
        // exists, and the acknowledgement tool's signal does not own the run.
        __test__.runningSubagents.get(cancel.details.id)!.abortController!.abort();
        await waitForDelivery(4);
      }
      results.delivered = delivered;
      if (!results.closedPanes) {
        results.closedPanes = calls()
          .filter((args) => args[0] === "kill-pane")
          .map((args) => args[2]);
      }
    } catch (error) {
      results.failure = String(error);
    } finally {
      await event("session_shutdown");
      // Disposed watchers must never deliver to a replacement or dead runtime.
      await new Promise((resolve) => setTimeout(resolve, 20));
      results.delivered = delivered;
      writeFileSync(join(root, "results.json"), JSON.stringify(results));
      realContext.shutdown();
    }
  });
}
