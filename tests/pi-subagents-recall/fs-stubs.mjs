// Real temporary-file IO, but no actual mux socket is required or inspected.
export * from "node:fs";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
export function statSync(path) {
  if (path !== "/offline/tmux") throw new Error("Unexpected mux socket inspection");
  const file = join(process.env.PI_RECALL_ROOT, "incarnation.json");
  const incarnation = existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : { dev: "1", ino: "2", ctimeNs: "3" };
  return { dev: BigInt(incarnation.dev), ino: BigInt(incarnation.ino), ctimeNs: BigInt(incarnation.ctimeNs), isSocket: () => true };
}
