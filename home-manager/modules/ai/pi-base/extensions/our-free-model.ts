import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const cost = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 };
const budgetLevels = {
  off: "light",
  minimal: "light",
  low: "light",
  medium: "balanced",
  high: "deep",
  xhigh: null,
  max: null,
};
const kiloLevels = {
  off: "disabled",
  minimal: null,
  low: "low",
  medium: "medium",
  high: "high",
  xhigh: null,
  max: null,
};

// Match the pinned proxy's catalog and 32K default output ceiling. Jev is a
// classifier, not a chat model; it must not be advertised through this API.
function model(
  id: string,
  name: string,
  contextWindow: number,
  image: boolean,
  thinkingLevelMap: Record<string, string | null> = budgetLevels,
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
    opencode: [
      model("deepseek-v4.1-flash-free", "DeepSeek V4.1 Flash (free)", 1048576, true, {
        off: "disabled",
        minimal: null,
        low: "low",
        medium: null,
        high: "high",
        xhigh: null,
        max: "max",
      }),
      model("glm-5.3-flash-free", "GLM 5.3 Flash (free)", 1048576, true, {
        off: null,
        minimal: null,
        low: "low",
        medium: null,
        high: "high",
        xhigh: null,
        max: "max",
      }),
      model("mimo-v2.6-flash-free", "MiMo V2.6 Flash (free)", 1048576, true),
      model("nemotron-3.5-super-vl-free", "Nemotron 3.5 Super VL (free)", 1048576, true, {
        ...kiloLevels,
        minimal: "minimal",
        xhigh: "xhigh",
      }),
      model("nemotron-3.5-lightning-free", "Nemotron 3.5 Lightning (free)", 128000, false),
      model("beam-free", "Beam (free)", 131072, false),
      model("flint-40b-free", "Flint 40B (free)", 131072, false),
      model("big-pickle", "Big Pickle (free)", 262144, true),
    ],
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
    // Supplying models replaces OpenCode's built-in paid catalog, so the
    // local free-pool key is never presented as access to paid models.
    pi.registerProvider(id, {
      baseUrl: `http://127.0.0.1:${port}/v1`,
      api: "openai-completions",
      apiKey: "!our-free-model-key",
      models,
    });
  }
}
