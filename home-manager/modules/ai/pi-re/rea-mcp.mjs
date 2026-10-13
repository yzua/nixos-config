// Register only the pinned REA server for this isolated root session.
import fs from "node:fs";
import path from "node:path";

export default function (pi) {
  const config = JSON.parse(fs.readFileSync(process.env.PI_RE_CONFIG, "utf8"));
  pi.registerMcpServer("rea", {
    command: config.python,
    args: [path.join(config.resources, "launcher.py"), "rea-mcp"],
    exposure: "codemode",
    timeout: 600,
    description:
      "REA native Ghidra, Android, JavaScript, artifacts, network and runtime evidence. Load reverse-engineer-anything; discover tools with searchTools().",
  });
}
