# Z.AI provider: config, environment variables, MCP services, and jq filters.
#
# Consolidates the Z.AI integration into a single module:
#   config    — API root, timeout, model identifiers
#   env       — Shell env var prefix and export block
#   services  — MCP service names and base URL
#   filters   — Agent-specific jq filters for secret injection
#
# Agent-local config; not shared with NixOS modules.

{
  lib ? null,
}:

let
  config = {
    apiRoot = "https://api.z.ai/api";
    timeout = 300000; # API timeout in ms (5 min)
    models = {
      haiku = "glm-5-turbo";
      sonnet = "glm-5.1";
      opus = "glm-5.1"; # Same model as sonnet — no dedicated opus-tier available
    };
  };

  baseUrl = "${config.apiRoot}/mcp";

  services = [
    {
      name = "web_search_prime";
      mcpKey = "web-search-prime";
    }
    {
      name = "web_reader";
      mcpKey = "web-reader";
    }
    {
      name = "zread";
      mcpKey = "zread";
    }
  ];

  envVars = [
    {
      name = "ANTHROPIC_BASE_URL";
      value = "${config.apiRoot}/anthropic";
    }
    {
      name = "API_TIMEOUT_MS";
      value = toString config.timeout;
    }
    {
      name = "ANTHROPIC_DEFAULT_HAIKU_MODEL";
      value = config.models.haiku;
    }
    {
      name = "ANTHROPIC_DEFAULT_SONNET_MODEL";
      value = config.models.sonnet;
    }
    {
      name = "ANTHROPIC_DEFAULT_OPUS_MODEL";
      value = config.models.opus;
    }
  ];

  # jq filter generation (requires lib)
  mkServiceEntries =
    {
      mcpRoot,
      type,
      extraFields ? { },
    }:
    lib.concatStringsSep " |\n    " (
      map (
        svc:
        let
          extraFieldLines = lib.mapAttrsToList (k: v: "${k}: ${v}") extraFields;
          objectLines = [
            (lib.optionalString (type != null) ''type: "${type}"'')
            ''url: "${baseUrl}/${svc.name}/mcp"''
            ''headers: { Authorization: ("Bearer " + $key) }''
          ]
          ++ extraFieldLines;
          renderedLines = lib.concatStringsSep ",\n            " (
            builtins.filter (line: line != "") objectLines
          );
        in
        ''
          .${mcpRoot}["${svc.mcpKey}"] = {
            ${renderedLines}
          }''
      ) services
    );

  mkZaiFilter =
    {
      mcpRoot,
      nativeKey,
      type,
      extraFields ? { },
    }:
    let
      serviceEntries = mkServiceEntries { inherit mcpRoot type extraFields; };
    in
    ''
      (if .${mcpRoot}["${nativeKey}"] != null then .${mcpRoot}["${nativeKey}"].${
        if mcpRoot == "mcp" then "environment" else "env"
      }.Z_AI_API_KEY = $key else . end) |
        ${serviceEntries}'';
in
{
  inherit
    config
    baseUrl
    services
    envVars
    ;

  # Inline bash prefix: VAR=val \  (for inline env before a command)
  inlinePrefix = builtins.concatStringsSep " \\\n  " (map (v: "${v.name}=\"${v.value}\"") envVars);

  # Export block: export VAR=val\n (for script embedding)
  exportBlock = builtins.concatStringsSep "\n" (map (v: "export ${v.name}=\"${v.value}\"") envVars);

  # Agent-specific jq filters for Z.AI MCP secret injection (requires lib)
  opencodeZaiFilter = mkZaiFilter {
    mcpRoot = "mcp";
    nativeKey = "zai-mcp-server";
    type = "remote";
  };
  claudeZaiFilter = mkZaiFilter {
    mcpRoot = "mcpServers";
    nativeKey = "zai-mcp-server";
    type = "http";
  };
  ompZaiFilter = mkZaiFilter {
    mcpRoot = "mcpServers";
    nativeKey = "zai-mcp-server";
    type = "http";
  };
  geminiZaiFilter = mkZaiFilter {
    mcpRoot = "mcpServers";
    nativeKey = "zai-mcp-server";
    type = "http";
    extraFields = {
      command = ''"echo"'';
      args = "[]";
    };
  };
}
