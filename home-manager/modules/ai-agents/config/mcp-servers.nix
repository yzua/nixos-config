# MCP server definitions and logging configuration.

{ config, lib, ... }:

let
  cfg = config.programs.aiAgents;
  zai = import ../helpers/_zai-services.nix;

  mkZaiRemoteMcp = path: {
    enable = true;
    type = "remote";
    url = "${zai.baseUrl}/${path}/mcp";
    headers = {
      Authorization = "Bearer {env:ZAI_API_KEY}";
    };
  };

  # Derive Z.AI MCP server entries from the services registry — single source of truth.
  zaiMcpServers = builtins.listToAttrs (
    map (svc: {
      name = svc.mcpKey;
      value = mkZaiRemoteMcp svc.name;
    }) zai.services
  );
in
{
  programs.aiAgents = {
    mcpServers =
      zaiMcpServers
      // {
        context7 = {
          enable = true;
          command = "bunx";
          args = [
            "@upstash/context7-mcp@2.1.2"
          ];
          env = {
            CONTEXT7_API_KEY = "__CONTEXT7_API_KEY_PLACEHOLDER__"; # patched at activation from sops secret
          };
        };

        github = {
          enable = true;
          command = "github-mcp-server";
          args = [
            "stdio"
            "--toolsets=default,actions,code_security,dependabot,secret_protection"
          ];
          env = {
            GITHUB_PERSONAL_ACCESS_TOKEN = "__GITHUB_TOKEN_PLACEHOLDER__"; # patched at activation via gh auth token
          };
        };

        semgrep = {
          enable = true;
          command = "semgrep";
          args = [
            "mcp"
          ];
        };

        chrome-devtools = {
          enable = true;
          command = "npx";
          args = [
            "-y"
            "chrome-devtools-mcp@latest"
            "--autoConnect"
          ];
        };

      }
      // lib.optionalAttrs cfg.agentmemory.enable {
        agentmemory = {
          enable = true;
          command = "bunx";
          args = [
            "--silent"
            "@agentmemory/mcp@${cfg.agentmemory.version}"
          ];
          env = {
            AGENTMEMORY_URL = cfg.agentmemory.url;
          };
        };
      };

    logging = {
      enable = true;
      directory = "${config.xdg.dataHome}/ai-agents/logs";
      notifyOnError = true;
      retentionDays = 30;

      enableOtel = false;
    };
  };
}
