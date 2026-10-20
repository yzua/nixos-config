# Own shared Pi resources and live configuration at its existing canonical location.
{
  aiPackages,
  config,
  lib,
  pkgs,
  setup,
  ...
}:
let
  base = import ./resources.nix { inherit aiPackages pkgs setup; };
  # Initialization policy only: preserve the original marker and later UI changes.
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
  runtime = pkgs.writeText "pi-base-runtime.json" (
    builtins.toJSON {
      agentDir = ".pi/agent";
      inherit (base) pi commonExtensions;
      profile = "pi-base";
      sessions = "pi-base/sessions";
      instructions = [ base.instructions ];
      skills = base.commonSkills;
    }
  );
in
{
  imports = [ ../chrome-devtools ];
  home.packages = [
    (pkgs.writeShellScriptBin "pi-base" ''
      exec ${pkgs.python3}/bin/python3 ${./launcher.py} ${runtime} "$@"
    '')
  ];
  home.file = {
    ".pi/agent/AGENTS.md".source = base.instructions;
    ".pi/agent/agents".source = ./agents;
  }
  // builtins.listToAttrs (
    map (name: {
      name = ".pi/agent/extensions/${name}";
      value.source = "${base.directory}/${name}";
    }) base.extensionNames
  );

  home.activation.initializePi = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    if [ -v DRY_RUN ]; then
      echo "Would initialize shared writable Pi settings and models"
    else
      ${pkgs.python3}/bin/python3 ${./initialize.py} \
        --agent-dir ${lib.escapeShellArg agentDir} \
        --state-dir ${lib.escapeShellArg "${config.xdg.stateHome}/pi-config"} \
        --defaults ${defaults}
    fi
  '';
}
