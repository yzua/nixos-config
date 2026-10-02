import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmdirSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import subagents, {
  __test__,
} from "../../home-manager/modules/ai/pi/extensions/interactive-subagents/pi-extension/subagents/index.ts";
import { inspectSubagentWriterLease } from "../../home-manager/modules/ai/pi/extensions/interactive-subagents/pi-extension/subagents/session.ts";

// Load through installed Pi and invoke its registered tools with fake tmux.
// Cleanup fault coverage also injects a real filesystem failure at its adapter.
// No child CLI or paid provider is executed.
export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, realContext) => {
    const root = process.env.PI_TEST_ROOT!;
    const results: Record<string, unknown> = {};
    const tools = new Map<string, { execute: (...args: unknown[]) => Promise<any> }>();
    const handlers = new Map<string, Array<(...args: unknown[]) => unknown>>();
    const delivered: Array<Record<string, any>> = [];
    const deliveryAttempts: string[] = [];
    let throwDelivery = false;
    let widgetUpdates = 0;
    let questionWakeups = 0;
    const unhandled: string[] = [];
    const reportUnhandled = (error: unknown) => unhandled.push(String(error));
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
        if (message.customType === "subagent_question") questionWakeups++;
        if (message.customType !== "subagent_result") return;
        deliveryAttempts.push((message.details as { name: string }).name);
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
    const waitForCleanup = async (id: string) => {
      const deadline = Date.now() + 4000;
      while (__test__.runningSubagents.has(id) && Date.now() < deadline)
        await new Promise((resolve) => setTimeout(resolve, 10));
      if (__test__.runningSubagents.has(id)) throw new Error(`Run ${id} did not settle`);
    };
    const owner = (session: string) => JSON.parse(readFileSync(`${session}.owner.json`, "utf8"));
    const writerState = (session: string) => {
      const claim = owner(session);
      return inspectSubagentWriterLease(session, claim.run.id, claim.token);
    };
    const finishWriter = (session: string) => {
      execFileSync("tmux", ["writer-finish", session]);
      if (writerState(session) !== "dead") throw new Error("Mock writer death not established");
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
        writeFileSync(join(root, "capture-delay"), "0.2");
        const disposed = await spawn("disposed");
        writeFileSync(
          `${disposed.details.sessionFile}.ask`,
          JSON.stringify({ question: "OLD_QUESTION" }),
        );
        await event("session_shutdown");
        widgetUpdates = 0;
        await new Promise((resolve) => setTimeout(resolve, 1100));
        results.postShutdownWidgets = widgetUpdates;
        results.questionWakeups = questionWakeups;
        unlinkSync(join(root, "capture-delay"));
        await event("session_start");
        mode("managed");
        await spawn("replacement");
        await waitForDelivery(1);
        await new Promise((resolve) => setTimeout(resolve, 50));
      } else if (scenario === "ownership-park") {
        mode("managed-live");
        const initial = await spawn("managed");
        writeFileSync(join(root, "parked-session"), initial.details.sessionFile);
        await event("session_shutdown");
        results.claimSurvives = existsSync(`${initial.details.sessionFile}.owner.json`);
        results.writerState = writerState(initial.details.sessionFile);
      } else if (scenario === "ownership-restart") {
        const session = readFileSync(join(root, "parked-session"), "utf8");
        mode("healthy");
        results.writerBeforeFollowup = writerState(session);
        results.liveFollowup = (await resume()).details;
        results.panesAfterLiveFollowup = readFileSync(join(root, "pane-count"), "utf8");
        // A closed detached pane plus a stale error sidecar must not poison
        // the next writer's result. Use the real pane-loss polling adapter.
        finishWriter(session);
        writeFileSync(join(root, "closed-%1"), "closed");
        writeFileSync(
          `${session}.exit`,
          JSON.stringify({ type: "error", errorMessage: "OLD_ERROR" }),
        );
        mode("managed");
        results.closedPaneResume = (await resume()).details;
        await waitForDelivery(1);
        results.ownerAfterCompletion = owner(session);
      } else if (scenario === "ownership-refusals") {
        mode("managed-live");
        const initial = await spawn("managed");
        if (writerState(initial.details.sessionFile) !== "live")
          throw new Error("Refusal coverage requires a live mock writer");
        await event("session_shutdown");
        await event("session_start");
        const file = `${initial.details.sessionFile}.owner.json`;
        const saved = readFileSync(file, "utf8");
        writeFileSync(file, "not JSON");
        results.corrupt = (await resume()).details;
        writeFileSync(file, JSON.stringify({ ...JSON.parse(saved), mux: "different-server" }));
        results.wrongMux = (await resume()).details;
        writeFileSync(file, saved);
        mkdirSync(`${initial.details.sessionFile}.owner.lock`);
        results.busy = (await resume()).details;
        rmdirSync(`${initial.details.sessionFile}.owner.lock`);
        mode("unavailable");
        results.unavailable = (await resume()).details;
        mode("capture-error");
        results.captureFailure = (await resume()).details;
        mode("healthy");
        writeFileSync(join(root, "capture-delay"), "4");
        const probeStarted = Date.now();
        results.slowCapture = (await resume()).details;
        results.slowCaptureMs = Date.now() - probeStarted;
        unlinkSync(join(root, "capture-delay"));
        results.claimPreserved = readFileSync(file, "utf8") === saved;
        results.panes = readFileSync(join(root, "pane-count"), "utf8");
      } else if (scenario === "ownership") {
        mode("managed-live");
        const initial = await spawn("managed");
        results.sessionFile = initial.details.sessionFile;
        await event("session_shutdown");
        await new Promise((resolve) => setTimeout(resolve, 30));
        await event("session_start");
        mode("healthy");
        results.writerBeforeFollowup = writerState(initial.details.sessionFile);
        results.detachedFollowup = (await resume()).details;
        results.panesAfterDetachedFollowup = readFileSync(join(root, "pane-count"), "utf8");
        results.claimSurvives = existsSync(`${initial.details.sessionFile}.owner.json`);
        // Terminal completion, not watcher disposal, settles the original run.
        finishWriter(initial.details.sessionFile);
        writeFileSync(join(root, "done-%1"), "done");
        await waitForDelivery(1);
        mode("managed");
        results.parallelResumes = (await Promise.all([resume(), resume()])).map((r) => r.details);
        await waitForDelivery(2);
        results.ownerAfterCompletion = owner(initial.details.sessionFile);
        mode("send-failure");
        try {
          await resume();
        } catch (error) {
          results.failedResume = String(error);
        }
        results.ownerAfterFailure = owner(initial.details.sessionFile);
        mode("managed");
        results.retry = (await resume()).details;
        await waitForDelivery(3);
      } else if (scenario === "cleanup-errors") {
        mode("managed-cleanup-fault");
        process.on("unhandledRejection", reportUnhandled);
        const initial = await spawn("managed");
        const lock = `${initial.details.sessionFile}.owner.lock`;
        // The synchronous kill adapter fills the held ownership lock, causing
        // a real ENOTEMPTY rather than replacing lifecycle helpers.
        await waitForDelivery(1);
        results.lockRetained = existsSync(lock);
        results.retry = (await resume()).details;
        results.unhandled = unhandled;
      } else if (scenario === "completion-errors") {
        mode("managed-error");
        await spawn("provider-error");
        await waitForDelivery(1);
        mode("managed-invalid");
        await spawn("extraction-error");
        await waitForDelivery(2);
        mode("managed");
        throwDelivery = true;
        const throwing = await spawn("delivery-error");
        await waitForCleanup(throwing.details.id);
        results.throwingOwner = owner(throwing.details.sessionFile);
        await event("session_shutdown");
        await event("session_start");
        results.throwingRecall = __test__.runningSubagents.get(throwing.details.id) ?? null;
        mode("healthy");
        const cancel = await spawn("cancelled");
        // Legacy internal cancellation coverage: no public cancel capability
        // exists, and the acknowledgement tool's signal does not own the run.
        __test__.runningSubagents.get(cancel.details.id)!.abortController!.abort();
        await waitForDelivery(3);
        results.deliveryAttempts = deliveryAttempts;
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
      process.removeListener("unhandledRejection", reportUnhandled);
      await event("session_shutdown");
      // Disposed watchers must never deliver to a replacement or dead runtime.
      await new Promise((resolve) => setTimeout(resolve, 20));
      results.delivered = delivered;
      writeFileSync(join(root, "results.json"), JSON.stringify(results));
      realContext.shutdown();
    }
  });
}
