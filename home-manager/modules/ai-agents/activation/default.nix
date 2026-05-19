# Home Manager activation scripts for AI agent setup and secret patching.

{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.programs.aiAgents;

  inherit (builtins) toJSON;

  mcpTransforms = import ../helpers/_mcp-transforms.nix { inherit cfg lib; };
  inherit (mcpTransforms) sharedMcpServers claudeMcpServers;

  settingsBuilders = import ../helpers/_settings-builders.nix { inherit cfg config lib; };
  opencodeProfiles = import ../helpers/_opencode-profiles.nix { inherit config; };
  inherit (settingsBuilders) claudeSettings;

  opencodeConfigPaths = map opencodeProfiles.configPath opencodeProfiles.names;
  opencodeConfigPathList = lib.concatMapStringsSep " " lib.escapeShellArg opencodeConfigPaths;

  zai = import ../helpers/_zai.nix { inherit lib; };
  inherit (zai)
    opencodeZaiFilter
    claudeZaiFilter
    ompZaiFilter
    geminiZaiFilter
    ;
  githubPlaceholderFilter = ''
    walk(if type == "string" then gsub("__GITHUB_TOKEN_PLACEHOLDER__"; $token) else . end)
  '';
  openrouterPlaceholderFilter = ''
    walk(if type == "string" then gsub("__OPENROUTER_API_KEY_PLACEHOLDER__"; $key) else . end)
  '';
  context7PlaceholderFilter = ''
    walk(if type == "string" then gsub("__CONTEXT7_API_KEY_PLACEHOLDER__"; $key) else . end)
  '';

  # Import helper modules
  # modules-check: manual-helper ./secrets.nix ./codex-setup.nix ./claude-setup.nix ./plugins.nix ./skills.nix
  secretPatching = import ./secrets.nix {
    inherit
      cfg
      pkgs
      lib
      opencodeConfigPathList
      opencodeZaiFilter
      claudeZaiFilter
      ompZaiFilter
      geminiZaiFilter
      githubPlaceholderFilter
      openrouterPlaceholderFilter
      context7PlaceholderFilter
      ;
  };
  codexConfig = import ./codex-setup.nix {
    inherit
      cfg
      pkgs
      lib
      sharedMcpServers
      ;
  };
  claudeConfig = import ./claude-setup.nix {
    inherit
      cfg
      pkgs
      lib
      toJSON
      claudeSettings
      claudeMcpServers
      ;
  };
  opencodeProfileNames = opencodeProfiles.names;

  pluginInstalls = import ./plugins.nix {
    inherit
      cfg
      pkgs
      lib
      opencodeProfileNames
      ;
  };
  skillInstallation = import ./skills.nix {
    inherit
      cfg
      lib
      pkgs
      toJSON
      opencodeProfileNames
      ;
  };

in
{
  config = lib.mkIf cfg.enable {
    home.activation = {
      # === Secret Patching ===
      # Runs after all config writers so keys can be injected last.
      patchAiAgentSecrets = secretPatching;

      # Remove nested example assets that some skill packs ship under ~/.agents/skills.
      # Codex scans for SKILL.md recursively and warns on these non-skill sample files.
      sanitizeInstalledSkills = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        sample_skill="$HOME/.agents/skills/engineering-advanced-skills/skill-tester/assets/sample-skill/SKILL.md"
        if [[ -f "$sample_skill" ]]; then
          rm -f "$sample_skill"
          echo "✓ Removed nested sample SKILL.md from installed skills"
        fi
      '';

      # === Skill Installation ===
      installAgentSkills = skillInstallation;

      # === Codex Configuration ===
      setupCodexConfig = codexConfig;

      # === Claude Configuration ===
      # Real files (not symlinks) so plugins can modify them.
      setupClaudeConfig = claudeConfig;

      # === Plugin Installation ===
      inherit (pluginInstalls)
        installImpeccable
        installAgencyAgents
        installEverythingClaudeCode
        cleanupDisabledAgencyAgents
        cleanupDisabledEverythingClaudeCode
        ;
    };
  };
}
