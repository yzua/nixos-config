// Process identities are fixture data, not real writers/processes to spawn/kill.
export * from "node:fs";
import { existsSync, readFileSync as readReal } from "node:fs";
import { join } from "node:path";
const fixture = (name, fallback) => {
  const path = join(process.env.PI_RECALL_ROOT, name);
  return existsSync(path) ? JSON.parse(readReal(path, "utf8")) : fallback;
};
export function readlinkSync(path) {
  if (path === "/proc/self/ns/pid") return "pid:[123]";
  throw new Error("Unexpected namespace identity read");
}
const denied = (code) => { const error = new Error(`offline /proc ${code}`); error.code = code; throw error; };
export function readFileSync(path, options) {
  if (path === "/etc/machine-id") return fixture("machine.json", "a".repeat(32));
  if (path === "/proc/sys/kernel/random/boot_id") return fixture("boot.json", "11111111-1111-4111-8111-111111111111");
  if (/^\/proc\/(?:self|\d+)\/stat$/.test(path)) {
    const mode = fixture("proc-mode.json", "live");
    if (mode === "proc-unavailable") return denied("EACCES");
    const pid = path === "/proc/self/stat" ? process.pid : Number(path.split("/")[2]);
    if (path !== "/proc/self/stat") {
      if (mode === "dead") return denied("ENOENT");
      if (mode === "unknown") return denied("EACCES");
      if (mode === "corrupt") return "not proc stat data";
    }
    const state = path !== "/proc/self/stat" && mode === "zombie" ? "Z" : "S";
    const start = path !== "/proc/self/stat" && mode === "reused" ? "102" : "101";
    return `${pid} (offline (writer)) ${state} ${Array(18).fill("0").join(" ")} ${start} 0 0\n`;
  }
  return readReal(path, options);
}
