# Package local Pi sources while keeping settings, models, and credentials writable.

{
  aiPackages,
  config,
  lib,
  pkgs,
  setup,
  ...
}:

let
  extensionResources = import ./extension-resources.nix { inherit pkgs setup; };
  # Initialization policy only: later activations preserve the writable profile.
  model = {
    api = "openai-responses";
    metadata = {
      id = "gpt-6.1-sol";
      name = "GPT-6.1 Sol";
      reasoning = true;
      thinkingLevelMap = {
        off = null;
        minimal = null;
        low = "low";
        medium = "medium";
        high = "high";
        xhigh = "xhigh";
        max = "max";
      };
    };
  };
  defaults = pkgs.writeText "pi-defaults.json" (
    builtins.toJSON {
      inherit model;
      settings = {
        defaultModel = model.metadata.id;
        defaultThinkingLevel = "high";
        extensions = [ "-builtin:mcp" ];
      };
    }
  );
  agentDir = "${config.home.homeDirectory}/.pi/agent";
  stateDir = "${config.xdg.stateHome}/pi-config";
in
{
  # Herdr cold restore calls `pi --session PATH`, not the original launcher.
  # Keep RE root sessions on pi-re without changing the pinned Pi executable.
  home.packages = [
    (lib.hiPrio (
      pkgs.writeShellScriptBin "pi" ''
        exec ${pkgs.python3}/bin/python3 ${./resume-dispatch.py} ${lib.getExe aiPackages.pi} -- "$@"
      ''
    ))
  ];

  home.file = {
    ".pi/agent/AGENTS.md".source = ./AGENTS.md;
    ".pi/agent/prompts".source = ./prompts;
    ".pi/agent/agents".source = ./agents;
    ".pi/agent/extensions/ask-user-question.ts".source =
      "${extensionResources}/lib/pi-config/ask-user-question.ts";
    ".pi/agent/extensions/network-diagnostics.ts".source =
      "${extensionResources}/lib/pi-config/network-diagnostics.ts";
    ".pi/agent/extensions/upstream-retry.ts".source =
      "${extensionResources}/lib/pi-config/upstream-retry.ts";
    ".pi/agent/extensions/prompt-snippets".source =
      "${extensionResources}/lib/pi-config/prompt-snippets";
    ".pi/agent/extensions/web-fetch".source = "${extensionResources}/lib/pi-config/web-fetch";
    ".pi/agent/extensions/web-search".source = "${extensionResources}/lib/pi-config/web-search";
    ".pi/agent/extensions/interactive-subagents".source =
      "${extensionResources}/lib/pi-config/interactive-subagents";
  };

  # The first activation applies agreed defaults. Later UI changes remain user-owned.
  home.activation.initializePi = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    if [ -v DRY_RUN ]; then
      echo "Would initialize writable Pi settings and models"
    else
      ${pkgs.python3}/bin/python3 ${./initialize.py} \
        --agent-dir ${lib.escapeShellArg agentDir} \
        --state-dir ${lib.escapeShellArg stateDir} \
        --defaults ${defaults}
    fi
  '';
}
