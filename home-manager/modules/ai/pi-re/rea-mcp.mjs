// Native MCP implementation with session-only REA; never read shared/project mcp.json.
import { createMcpExtension } from "@earendil-works/pi-coding-agent";
import fs from "node:fs";
import path from "node:path";

export default function (pi) {
  const config = JSON.parse(fs.readFileSync(process.env.PI_RE_CONFIG, "utf8"));
  const state = process.env.XDG_STATE_HOME || path.join(process.env.HOME, ".local/state");
  createMcpExtension({
    loadConfig: () => ({ servers: [], errors: [], autoEnableCodemode: true }),
    logPath: path.join(state, "pi-re/mcp.log"),
  })(pi);
  pi.registerMcpServer("rea", {
    command: config.python,
    args: [path.join(config.resources, "launcher.py"), "rea-mcp"],
    exposure: "codemode",
    timeout: 600,
    description:
      "REA native Ghidra, Android, JavaScript, artifacts, network and runtime evidence. Load reverse-engineer-anything; discover tools with searchTools().",
  });
}
