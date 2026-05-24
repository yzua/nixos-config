# Home Manager activation scripts for AI agent setup and secret patching.

{
  config,
  inputs,
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
  herdrPackage = inputs.herdr.packages.${pkgs.stdenv.hostPlatform.system}.default;
  herdrSource = inputs.herdr.outPath;
  herdrIntegrationTargets = lib.concatStringsSep " " (
    map lib.escapeShellArg cfg.herdr.installIntegrations
  );

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

      cleanupRetiredGeminiCli = lib.mkIf (!cfg.gemini.enable) (
        lib.hm.dag.entryAfter [ "linkGeneration" ] ''
          gemini_cfg="$HOME/.gemini/settings.json"
          if [[ -f "$gemini_cfg" ]] && ${pkgs.jq}/bin/jq -e '
            (.policyPaths // []) == ["$HOME/.gemini/policies"]
            or (.ui.customThemes.Gruvbox.name // "") == "Gruvbox"
          ' "$gemini_cfg" >/dev/null 2>&1; then
            rm -f "$gemini_cfg"
            echo "✓ Removed retired Gemini CLI settings"
          fi
        ''
      );

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

      installHerdrSkill = lib.mkIf cfg.herdr.enable (
        lib.hm.dag.entryAfter
          [
            "installAgentSkills"
            "installImpeccable"
            "installEverythingClaudeCode"
          ]
          ''
            herdr_skill_source=${lib.escapeShellArg "${herdrSource}/SKILL.md"}

            install_herdr_skill() {
              local target_dir="$1"
              mkdir -p "$target_dir"
              cp "$herdr_skill_source" "$target_dir/SKILL.md"
              chmod 644 "$target_dir/SKILL.md"
            }

            ${lib.optionalString cfg.claude.enable ''
              install_herdr_skill "$HOME/.claude/skills/herdr"
            ''}
            ${lib.optionalString cfg.codex.enable ''
              install_herdr_skill "$HOME/.codex/skills/herdr"
            ''}
            ${lib.optionalString cfg.gemini.enable ''
              install_herdr_skill "$HOME/.gemini/skills/herdr"
            ''}
            ${lib.optionalString cfg.opencode.enable ''
              for profile in ${lib.concatStringsSep " " (map lib.escapeShellArg opencodeProfileNames)}; do
                install_herdr_skill "$HOME/.config/$profile/skills/herdr"
              done
            ''}

            echo "✓ Herdr agent skill installed"
          ''
      );

      # === Codex Configuration ===
      setupCodexConfig = codexConfig;

      # === Claude Configuration ===
      # Real files (not symlinks) so plugins can modify them.
      setupClaudeConfig = claudeConfig;

      installHerdrIntegrations = lib.mkIf cfg.herdr.enable (
        lib.hm.dag.entryAfter
          [
            "setupClaudeConfig"
            "setupCodexConfig"
            "writeBoundary"
          ]
          ''
            herdr_bin=${lib.escapeShellArg "${herdrPackage}/bin/herdr"}

            mkdir -p "$HOME/.config/herdr"
            ${lib.optionalString cfg.omp.enable ''
              mkdir -p "$HOME/.omp/agent/extensions"
            ''}
            ${lib.optionalString cfg.opencode.enable ''
              for profile in ${lib.concatStringsSep " " (map lib.escapeShellArg opencodeProfileNames)}; do
                mkdir -p "$HOME/.config/$profile/plugins"
              done
            ''}

            ${lib.optionalString (cfg.herdr.installIntegrations != [ ]) ''
              for target in ${herdrIntegrationTargets}; do
                if [[ "$target" == "opencode" ]]; then
                  ${lib.optionalString cfg.opencode.enable ''
                    echo "✓ Herdr opencode integration managed declaratively for all Home Manager OpenCode profiles"
                  ''}
                  ${lib.optionalString (!cfg.opencode.enable) ''
                    echo "⚠ Herdr opencode integration requested but OpenCode is disabled; skipping" >&2
                  ''}
                  continue
                fi

                if "$herdr_bin" integration install "$target" >/tmp/herdr-integration-"$target".log 2>&1; then
                  echo "✓ Herdr $target integration installed"
                else
                  echo "⚠ Herdr $target integration install failed; continuing Home Manager activation" >&2
                  sed 's/^/  /' /tmp/herdr-integration-"$target".log >&2 || true
                fi
              done
            ''}
          ''
      );

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
