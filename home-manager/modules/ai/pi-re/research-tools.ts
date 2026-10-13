/** Bounded source reads for dedicated research workers; never shell/edit/runtime tools. */
import * as fs from "node:fs/promises";
import * as path from "node:path";
import { constants } from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const ALLOWED = new Set(["research_read", "research_list", "web_search", "web_fetch"]);
const PRIVATE =
  /^(?:\.git|\.pi|\.env(?:\..*)?|auth\.json|models\.json|credentials(?:\..*)?|.*\.(?:pem|key|p12|pfx))$/i;

export default function (pi: ExtensionAPI) {
  const root = process.env.PI_RE_RESEARCH_ROOT;
  if (process.env.PI_RE_RESEARCH !== "1" || !root || !path.isAbsolute(root)) {
    throw new Error("Research tools require their dedicated read-only worker profile");
  }
  pi.on("tool_call", (event) => {
    if (!ALLOWED.has(event.toolName)) {
      return { block: true, reason: "This research worker has only source-reading and web tools" };
    }
  });

  async function resolveSource(requested: string): Promise<string> {
    const candidate = path.resolve(root!, requested);
    const relative = path.relative(root!, candidate);
    if (relative.startsWith(".." + path.sep) || relative === ".." || path.isAbsolute(relative)) {
      throw new Error("Select a path within this worker's pinned source directory");
    }
    if (relative.split(path.sep).some((part) => PRIVATE.test(part))) {
      throw new Error("Private configuration/key paths are excluded from source review");
    }
    const real = await fs.realpath(candidate);
    if (real !== candidate || (await fs.realpath(root!)) !== root) {
      throw new Error("Source-review paths must not contain symlinks");
    }
    return candidate;
  }

  pi.registerTool({
    name: "research_read",
    label: "Read research source",
    description:
      "Read bounded UTF-8 text inside the pinned source directory; private configuration/key paths and symlinks are excluded.",
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
    parameters: Type.Object({
      path: Type.String({ minLength: 1, maxLength: 4096 }),
      offset: Type.Optional(Type.Integer({ minimum: 1, maximum: 1000000 })),
      limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 2000 })),
    }),
    async execute(_id, params) {
      const source = await resolveSource(params.path);
      const file = await fs.open(
        source,
        constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK,
      );
      try {
        const info = await file.stat();
        if (!info.isFile() || info.size > 1024 * 1024) {
          throw new Error("Source reads require a regular text file of at most 1 MiB");
        }
        const bytes = Buffer.alloc(1024 * 1024 + 1);
        const { bytesRead } = await file.read(bytes, 0, bytes.length, 0);
        const content = bytes.subarray(0, bytesRead);
        if (bytesRead > 1024 * 1024 || content.includes(0)) {
          throw new Error("Source read exceeded its byte budget or contains binary data");
        }
        const text = new TextDecoder("utf-8", { fatal: true }).decode(content);
        const lines = text.split("\n");
        const start = (params.offset ?? 1) - 1;
        const selected = lines.slice(start, start + (params.limit ?? 200));
        const output = Buffer.from(selected.join("\n"))
          .subarray(0, 64 * 1024)
          .toString("utf8");
        return {
          content: [{ type: "text", text: output }],
          details: {
            path: source,
            offset: start + 1,
            totalLines: lines.length,
            truncated:
              Buffer.byteLength(selected.join("\n")) > 64 * 1024 ||
              start + selected.length < lines.length,
          },
        };
      } finally {
        await file.close();
      }
    },
  });

  pi.registerTool({
    name: "research_list",
    label: "List research sources",
    description:
      "List up to 200 entries in one directory inside the pinned source root, excluding private configuration/key names and symlinks.",
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
    parameters: Type.Object({ path: Type.Optional(Type.String({ maxLength: 4096 })) }),
    async execute(_id, params) {
      const source = await resolveSource(params.path ?? ".");
      const directory = await fs.opendir(source);
      const entries: string[] = [];
      let truncated = false;
      try {
        for await (const entry of directory) {
          if (entry.isSymbolicLink() || PRIVATE.test(entry.name)) continue;
          if (entries.length === 200) {
            truncated = true;
            break;
          }
          entries.push(entry.name + (entry.isDirectory() ? "/" : ""));
        }
      } finally {
        // for-await closes the handle, including on early break.
      }
      return {
        content: [{ type: "text", text: entries.sort().join("\n") }],
        details: { path: source, truncated },
      };
    },
  });
}
