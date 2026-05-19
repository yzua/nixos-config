# Generates a shell-sourceable config file with model IDs and service endpoints.
# Bridges the Nix single-source-of-truth (_models.nix, constants.nix) to runtime
# shell scripts (scripts/ai/_agent-registry.sh).
# Written to ~/.config/ai-agents/models.sh by files.nix.

let
  models = import ./_models.nix;
  zai = import ./_zai.nix { };

  lines = [
    "# Auto-generated model and service config — do not edit."
    "# Regenerate with: just home"
    "# Source: shared/constants.nix, home-manager/modules/ai-agents/helpers/_models.nix"
    ""
    "# Model IDs (source: helpers/_models.nix)"
    "AI_MODEL_GPT_LOW='${models.gpt-low}'"
    "AI_MODEL_GPT_DEFAULT='${models.gpt-default}'"
    "AI_MODEL_GPT_XHIGH='${models.gpt-xhigh}'"
    ""
    "# ZAI service config (source: helpers/_zai.nix)"
    "ZAI_API_ROOT='${zai.config.apiRoot}'"
    "ZAI_TIMEOUT='${toString zai.config.timeout}'"
    "ZAI_MODEL_HAIKU='${zai.config.models.haiku}'"
    "ZAI_MODEL_SONNET='${zai.config.models.sonnet}'"
    "ZAI_MODEL_OPUS='${zai.config.models.opus}'"
  ];
in
builtins.concatStringsSep "\n" lines + "\n"
