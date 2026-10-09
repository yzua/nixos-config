# Package local Pi sources while keeping settings, models, and credentials writable.

{
  aiPackages,
  config,
  lib,
  pkgs,
  ...
}:

let
  # Web-fetch is the only extension with external dependencies. Fetch its lock,
  # then assemble the complete local extension resource bundle below.
  extensionResources = pkgs.buildNpmPackage {
    pname = "pi-personal-extensions";
    version = "local";
    src = ./extensions/web-fetch;
    npmDepsHash = "sha256-Rbdj6jd25Urxr1wJj1Vl7mefv1IKu5zQhHgt6dOEqaU=";
    npmFlags = [ "--ignore-scripts" ];
    dontNpmBuild = true;
    installPhase = ''
      runHook preInstall
      resources="$out/lib/pi-config"
      mkdir -p "$resources/web-fetch" "$resources/prompt-snippets"
      cp -r node_modules "$resources/web-fetch/"
      cp index.ts package.json "$resources/web-fetch/"
      cp ${./extensions/ask-user-question.ts} "$resources/ask-user-question.ts"
      cp -r ${./extensions/prompt-snippets}/. "$resources/prompt-snippets/"
      cp -r ${./extensions/interactive-subagents} "$resources/interactive-subagents"
      runHook postInstall
    '';
  };
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
    ".pi/agent/extensions/prompt-snippets".source =
      "${extensionResources}/lib/pi-config/prompt-snippets";
    ".pi/agent/extensions/web-fetch".source = "${extensionResources}/lib/pi-config/web-fetch";
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
