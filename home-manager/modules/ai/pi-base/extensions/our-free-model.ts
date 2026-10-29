import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const cost = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 };
const kiloLevels = {
  off: "disabled",
  minimal: null,
  low: "low",
  medium: "medium",
  high: "high",
  xhigh: null,
  max: null,
};

// Kilo stays on the local proxy; OpenCode is owned by the official-CLI bridge.
function model(
  id: string,
  name: string,
  contextWindow: number,
  image: boolean,
  thinkingLevelMap: Record<string, string | null> = kiloLevels,
) {
  const input: ("text" | "image")[] = image ? ["text", "image"] : ["text"];
  return {
    id,
    name,
    input,
    cost,
    reasoning: true,
    contextWindow,
    maxTokens: 32768,
    thinkingLevelMap,
  };
}

export default function (pi: ExtensionAPI) {
  const stateHome = process.env.XDG_STATE_HOME || join(homedir(), ".local/state");
  let port = 18900;
  try {
    const settings = JSON.parse(
      readFileSync(join(stateHome, "our-free-model/settings.json"), "utf8"),
    );
    if (
      Number.isInteger(settings.standalonePort) &&
      settings.standalonePort > 0 &&
      settings.standalonePort <= 65535
    ) {
      port = settings.standalonePort;
    }
  } catch {
    // The service has not started yet; keep the configured default port.
  }
  const providers = {
    "kilo-free": [
      model("kilo-auto/free", "Kilo Auto Free", 256000, false, { ...kiloLevels, off: null }),
      model("reflection/beam-free", "Reflection Beam (free)", 1048576, false, kiloLevels),
      model(
        "nvidia/nemotron-3.5-super-vl:free",
        "Nemotron 3.5 Super VL (free)",
        1000000,
        true,
        kiloLevels,
      ),
    ],
  };
  for (const [id, models] of Object.entries(providers)) {
    // The local key grants access only to the selected anonymous Kilo pool.
    pi.registerProvider(id, {
      baseUrl: `http://127.0.0.1:${port}/v1`,
      api: "openai-completions",
      apiKey: "!our-free-model-key",
      models,
    });
  }
}
