# Per-agent settings builders and profile variant overrides.

{
  cfg,
  config,
  lib,
}:

let
  mcpTransforms = import ./_mcp-transforms.nix { inherit cfg lib; };
  formatterRegistry = import ./_formatters.nix;
  opencodeProfiles = import ./_opencode-profiles.nix { inherit config; };
  inherit (mcpTransforms)
    opencodeMcpServers
    ompMcpServers
    geminiMcpServers
    opencodeAndroidReMcpServers
    opencodeWebReMcpServers
    ;
  opencodeFormatterSettings = builtins.listToAttrs (
    map (formatter: {
      name = formatter.tool;
      value = {
        command = lib.splitString " " formatter.command;
        inherit (formatter) extensions;
      };
    }) formatterRegistry.formatters
  );

  mkOptionalOpencodeSetting =
    key: value:
    if builtins.isAttrs value then
      lib.optionalAttrs (value != { }) { ${key} = value; }
    else if builtins.isList value then
      lib.optionalAttrs (value != [ ]) { ${key} = value; }
    else
      lib.optionalAttrs (value != null) { ${key} = value; };

  claudeSettings = {
    inherit (cfg.claude) model permissions hooks;
    env =
      cfg.claude.env
      // (lib.optionalAttrs cfg.logging.enableOtel {
        CLAUDE_CODE_ENABLE_TELEMETRY = "1";
        OTEL_METRICS_EXPORTER = cfg.logging.otelExporter;
        OTEL_EXPORTER_OTLP_ENDPOINT = cfg.logging.otelEndpoint;
      });
  }
  // (lib.optionalAttrs (cfg.claude.extraSettings != { }) cfg.claude.extraSettings);

  ompSettings = {
    mcpServers = ompMcpServers;
  }
  // (lib.optionalAttrs (cfg.omp.extraSettings != { }) cfg.omp.extraSettings);

  opencodeSettings = {
    "$schema" = "https://opencode.ai/config.json";
    inherit (cfg.opencode) model;
    mcp = opencodeMcpServers;
    plugin = cfg.opencode.plugins;
    provider = cfg.opencode.providers;
    # Disable snapshot system to prevent tmp_pack_* file leaks and disk bloat (#14811)
    snapshot = false;
    # Suppress INFO permission spam (128KB per check × thousands per message)
    logLevel = "WARN";
    # Auto-compact context to prevent overflow on long sessions
    compaction = {
      auto = true;
      prune = true;
      reserved = 12000;
      tail_turns = 4;
      preserve_recent_tokens = 12000;
    };
    tool_output = {
      max_bytes = 50000;
      max_lines = 2000;
    };
    watcher.ignore = [
      "node_modules/**"
      "dist/**"
      ".git/**"
      ".venv/**"
      "target/**"
      "build/**"
      "coverage/**"
      "__pycache__/**"
      ".next/**"
      "result/**"
    ];
  }
  // (mkOptionalOpencodeSetting "permission" cfg.opencode.permission)
  // (mkOptionalOpencodeSetting "agent" cfg.opencode.agent)
  // (mkOptionalOpencodeSetting "command" cfg.opencode.command)
  // (mkOptionalOpencodeSetting "lsp" cfg.opencode.lsp)
  // (mkOptionalOpencodeSetting "formatter" (
    if cfg.opencode.formatter == { } then opencodeFormatterSettings else cfg.opencode.formatter
  ))
  // (mkOptionalOpencodeSetting "experimental" cfg.opencode.experimental)
  // (mkOptionalOpencodeSetting "default_agent" cfg.opencode.defaultAgent)
  // (mkOptionalOpencodeSetting "enabled_providers" cfg.opencode.enabledProviders)
  // (mkOptionalOpencodeSetting "disabled_providers" cfg.opencode.disabledProviders)
  // (lib.optionalAttrs (cfg.globalInstructions != "") { instructions = [ cfg.globalInstructions ]; })
  // (lib.optionalAttrs (cfg.opencode.extraSettings != { }) cfg.opencode.extraSettings);

  geminiSettings = {
    mcpServers = geminiMcpServers;
  }
  // (lib.optionalAttrs (cfg.globalInstructions != "") {
    systemInstruction = cfg.globalInstructions;
  })
  // (lib.optionalAttrs (cfg.gemini.extraSettings != { }) cfg.gemini.extraSettings);

  # Override agent-level model fields to match the profile's top-level model.
  # OpenCode's deep merge preserves agent-level models from the global config even when
  # OPENCODE_CONFIG_DIR loads a profile config without them, so we must explicitly set
  # each agent's model to the profile model to override the defaults at runtime.
  overrideAgentModels =
    model: agents:
    if agents == null || agents == { } then
      agents
    else
      builtins.mapAttrs (_name: agent: agent // { inherit model; }) agents;

  # Derived from _opencode-profiles.nix — single source of truth for profile→model mapping.
  opencodeSettingsByProfile = builtins.listToAttrs (
    map (
      { name, model, ... }:
      {
        inherit name;
        value =
          if model == null then
            opencodeSettings
          else
            opencodeSettings
            // {
              inherit model;
            }
            // (lib.optionalAttrs (opencodeSettings ? agent) {
              agent = overrideAgentModels model opencodeSettings.agent;
            });
      }
    ) opencodeProfiles.profiles
  );
in
{
  inherit
    claudeSettings
    ompSettings
    opencodeSettings
    geminiSettings
    opencodeSettingsByProfile
    opencodeAndroidReMcpServers
    opencodeWebReMcpServers
    ;
}
