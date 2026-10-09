import { existsSync, readFileSync, rmSync } from "node:fs";
import { readScreenAsync, surfaceExists } from "./tmux.ts";
import { isHerdrSurface } from "./herdr.ts";

/** Protocol evidence is independent of the diagnostic presented to the user.
 * An error sidecar can precede writer exit. Pane loss needs writer-death proof;
 * a monitor outage is never pane-loss proof. Claim and recall apply their own
 * intentionally different ownership policies to this evidence.
 */
interface PollResult {
  reason: "done" | "sentinel" | "error";
  evidence: "sidecar" | "terminal" | "sentinel-file" | "pane-lost" | "monitor-unavailable";
  exitCode: number;
  errorMessage?: string;
}

export function terminalExit(screen: string): PollResult | undefined {
  const match = screen.match(/__SUBAGENT_DONE_(\d+)__/);
  return match
    ? { reason: "sentinel", evidence: "terminal", exitCode: parseInt(match[1], 10) }
    : undefined;
}

function readExitSidecar(sessionFile?: string): PollResult | undefined {
  if (!sessionFile) return undefined;
  try {
    const file = `${sessionFile}.exit`;
    if (!existsSync(file)) return undefined;
    const data = JSON.parse(readFileSync(file, "utf-8"));
    rmSync(file, { force: true });
    if (data?.type === "error") {
      const errorMessage =
        typeof data.errorMessage === "string" && data.errorMessage.trim() !== ""
          ? data.errorMessage
          : "Subagent exited with stopReason=error (no errorMessage in sidecar).";
      return { reason: "error", evidence: "sidecar", exitCode: 1, errorMessage };
    }
    return { reason: "done", evidence: "sidecar", exitCode: 0 };
  } catch {
    return undefined;
  }
}

/** Supervision protocol polling, not a terminal operation. No exit sidecar
 * or Claude Stop file is consulted by the claim probe (it omits these paths).
 * Recall uses terminalExit on its bounded read, without consuming sidecars.
 */
export async function pollForExit(
  surface: string,
  signal: AbortSignal,
  options: {
    interval: number;
    sessionFile?: string;
    sentinelFile?: string;
    onTick?: (elapsed: number) => void;
  },
): Promise<PollResult> {
  const start = Date.now();
  let paneUnavailableSince: number | undefined;
  const paneLossGraceMs = 2000;
  for (;;) {
    if (signal.aborted) throw new Error("Aborted while waiting for subagent to finish");
    const sidecar = readExitSidecar(options.sessionFile);
    if (sidecar) return sidecar;
    if (options.sentinelFile) {
      try {
        if (existsSync(options.sentinelFile))
          return { reason: "sentinel", evidence: "sentinel-file", exitCode: 0 };
      } catch {}
    }
    try {
      const screen = await readScreenAsync(surface, 5);
      paneUnavailableSince = undefined;
      const exit = terminalExit(screen);
      if (exit) return exit;
    } catch {
      const sidecar = readExitSidecar(options.sessionFile);
      if (sidecar) return sidecar;
      let paneExists: boolean | undefined;
      try {
        paneExists = await surfaceExists(surface);
      } catch {}
      if (paneExists) paneUnavailableSince = undefined;
      else {
        paneUnavailableSince ??= Date.now();
        if (Date.now() - paneUnavailableSince >= paneLossGraceMs) {
          return {
            reason: "error",
            evidence: paneExists === false ? "pane-lost" : "monitor-unavailable",
            exitCode: 1,
            errorMessage:
              paneExists === false
                ? `Subagent pane ${surface} disappeared before reporting completion.`
                : `Cannot monitor subagent pane ${surface}: ${isHerdrSurface(surface) ? "Herdr" : "tmux"} is unavailable.`,
          };
        }
      }
    }
    options.onTick?.(Math.floor((Date.now() - start) / 1000));
    await new Promise<void>((resolve, reject) => {
      if (signal.aborted) return reject(new Error("Aborted"));
      const timer = setTimeout(() => {
        signal.removeEventListener("abort", onAbort);
        resolve();
      }, options.interval);
      function onAbort() {
        clearTimeout(timer);
        reject(new Error("Aborted"));
      }
      signal.addEventListener("abort", onAbort, { once: true });
    });
  }
}
