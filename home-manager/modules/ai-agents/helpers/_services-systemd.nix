{
  cfg,
  config,
  lib,
  pkgs,
  logCleanupCommand,
  mkCliAutoupdateScript,
  hmSystemdHelpers,
}:
let
  inherit (hmSystemdHelpers) mkHmTimer;
  agentmemoryRuntime = import ./_agentmemory-runtime.nix { inherit pkgs; };

  autoUpdateTools = [
    {
      binary = "claude";
      npmPackage = "@anthropic-ai/claude-code";
      label = "Claude Code CLI";
    }
    {
      binary = "codex";
      npmPackage = "@openai/codex";
      label = "Codex CLI";
    }
    {
      binary = "gemini";
      npmPackage = "@google/gemini-cli";
      label = "Gemini CLI";
    }
    {
      binary = "omp";
      npmPackage = "@oh-my-pi/pi-coding-agent";
      label = "Oh My Pi CLI";
    }
  ];

  mkAutoUpdateService =
    {
      binary,
      npmPackage,
      label,
    }:
    {
      Unit.Description = "Auto-update ${label}";
      Service = {
        Type = "oneshot";
        ExecStart = "${mkCliAutoupdateScript { inherit binary npmPackage label; }}";
      };
    };

  agentmemoryService = {
    Unit = {
      Description = "Shared persistent memory server for AI agents";
      After = [ "network-online.target" ];
    };
    Service = {
      Type = "simple";
      WorkingDirectory = "%h";
      Environment = [
        "AGENTMEMORY_URL=${cfg.agentmemory.url}"
        "CI=1"
        "NPM_CONFIG_CACHE=%h/.cache/npm"
        "PATH=${agentmemoryRuntime.iiiEngine}/bin:${pkgs.nodejs}/bin:/run/current-system/sw/bin"
      ];
      ExecStart = "${pkgs.nodejs}/bin/npx -y @agentmemory/agentmemory@${cfg.agentmemory.version}";
      Restart = "always";
      RestartSec = "10s";
    };
    Install.WantedBy = [ "default.target" ];
  };
in
lib.mkMerge [
  (lib.mkIf cfg.agentmemory.enable {
    services.agentmemory = agentmemoryService;
  })

  (lib.mkIf cfg.logging.enable {
    tmpfiles.rules = [
      "d ${cfg.logging.directory} 0755 - - -"
    ];

    services = {
      ai-agent-log-cleanup = {
        Unit.Description = "Clean up old AI agent logs";
        Service = {
          Type = "oneshot";
          ExecStart = "${pkgs.writeShellScript "cleanup" logCleanupCommand}";
        };
      };

      opencode-db-vacuum = {
        Unit.Description = "Vacuum OpenCode SQLite database";
        Service = {
          Type = "oneshot";
          ExecStart = "${pkgs.writeShellScript "opencode-vacuum" ''
            DB="${config.xdg.dataHome}/opencode/opencode.db"
            if [[ -f "$DB" ]]; then
              ${pkgs.sqlite}/bin/sqlite3 "$DB" "VACUUM;"
              echo "Vacuumed OpenCode database"
            fi
          ''}";
        };
      };
    }
    // builtins.listToAttrs (
      map (tool: lib.nameValuePair "${tool.binary}-autoupdate" (mkAutoUpdateService tool)) autoUpdateTools
    );

    timers = {
      ai-agent-log-cleanup = mkHmTimer { description = "Weekly AI agent log cleanup"; };
      opencode-db-vacuum = mkHmTimer { description = "Weekly OpenCode database vacuum"; };
    }
    // builtins.listToAttrs (
      map (
        tool:
        lib.nameValuePair "${tool.binary}-autoupdate" (mkHmTimer {
          description = "Weekly ${tool.label} auto-update";
        })
      ) autoUpdateTools
    );
  })
]
