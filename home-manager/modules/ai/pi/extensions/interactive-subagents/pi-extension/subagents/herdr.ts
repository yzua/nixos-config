/** Herdr surface operations. Always use inherited socket and explicit pane IDs. */
import { execFile, execFileSync } from "node:child_process";
import { promisify } from "node:util";
import { statSync } from "node:fs";

const execFileAsync = promisify(execFile);
// execFileSync forwards stderr on failure unless stdio is explicit, even when
// the caller catches the error (e.g. resume cleanup of an already-closed pane).
// Capture diagnostics for the caller without writing over Pi's terminal UI.
const options = { encoding: "utf8" as const, timeout: 5000, stdio: "pipe" as const };

export function isHerdrContext(): boolean {
  return process.env.HERDR_ENV === "1";
}

export function herdrConfigured(): boolean {
  return !!process.env.HERDR_SOCKET_PATH && !!process.env.HERDR_PANE_ID;
}

export function isHerdrSurface(surface: string): boolean {
  // Herdr's public IDs use its bijective base-32 alphabet, not decimal numbers.
  return /^w[0-9A-HJKMNP-TV-Z]+:p[0-9A-HJKMNP-TV-Z]+$/.test(surface);
}

export function herdrIdentity(): string {
  const socket = process.env.HERDR_SOCKET_PATH!;
  const stat = statSync(socket, { bigint: true });
  if (!stat.isSocket()) throw new Error("Herdr endpoint is not a Unix socket");
  // A restarted server can reuse the pathname and pane IDs. Fail closed on
  // socket replacement before reading or closing any previously owned pane.
  return `herdr:${socket}:${stat.dev}:${stat.ino}:${stat.ctimeNs}`;
}

export function createHerdrTab(name: string): string {
  const parent = process.env.HERDR_PANE_ID!;
  // Resolve the live caller, not the UI-focused workspace or the inherited
  // workspace ID (which can be stale after a pane move).
  const caller = JSON.parse(execFileSync("herdr", ["pane", "get", parent], options));
  const workspace = caller.result?.pane?.workspace_id;
  if (typeof workspace !== "string" || !/^w[0-9A-HJKMNP-TV-Z]+$/.test(workspace)) {
    throw new Error("Cannot determine the calling Herdr pane's workspace");
  }
  const response = JSON.parse(
    execFileSync(
      "herdr",
      [
        "tab",
        "create",
        "--workspace",
        workspace,
        "--cwd",
        process.cwd(),
        "--label",
        name,
        "--no-focus",
      ],
      options,
    ),
  );
  const pane = response.result?.root_pane?.pane_id;
  if (typeof pane !== "string" || !isHerdrSurface(pane)) {
    throw new Error(`Unexpected Herdr tab response: ${JSON.stringify(response)}`);
  }
  return pane;
}

export function createHerdrSurface(direction: "right" | "down", parent?: string): string {
  const response = JSON.parse(
    execFileSync(
      "herdr",
      [
        "pane",
        "split",
        parent ?? process.env.HERDR_PANE_ID!,
        "--direction",
        direction,
        "--cwd",
        process.cwd(),
        "--no-focus",
      ],
      options,
    ),
  );
  const pane = response.result?.pane?.pane_id;
  if (typeof pane !== "string" || !isHerdrSurface(pane)) {
    throw new Error(`Unexpected Herdr split response: ${JSON.stringify(response)}`);
  }
  return pane;
}

export function sendHerdrCommand(surface: string, command: string): void {
  // Atomic literal text + Enter; never route input through the outer tmux pane.
  execFileSync("herdr", ["pane", "run", surface, command], options);
}

export function readHerdrScreen(surface: string, lines: number): string {
  return execFileSync(
    "herdr",
    [
      "pane",
      "read",
      surface,
      "--source",
      "recent-unwrapped",
      "--format",
      "text",
      "--lines",
      String(Math.max(1, lines)),
    ],
    options,
  );
}

export async function readHerdrScreenAsync(surface: string, lines: number): Promise<string> {
  const { stdout } = await execFileAsync(
    "herdr",
    [
      "pane",
      "read",
      surface,
      "--source",
      "recent-unwrapped",
      "--format",
      "text",
      "--lines",
      String(Math.max(1, lines)),
    ],
    options,
  );
  return stdout;
}

export function closeHerdrSurface(surface: string): void {
  execFileSync("herdr", ["pane", "close", surface], options);
}

export async function herdrSurfaceExists(surface: string): Promise<boolean> {
  const { stdout } = await execFileAsync("herdr", ["pane", "list"], options);
  const response = JSON.parse(stdout);
  if (!Array.isArray(response.result?.panes)) throw new Error("Invalid Herdr pane list");
  return response.result.panes.some((pane: { pane_id: string }) => pane.pane_id === surface);
}
