# Home file and XDG config file declarations for AI agents.

{
  config,
  constants,
  inputs,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.programs.aiAgents;

  inherit (builtins) toJSON;

  fileTemplates = import ./helpers/_file-templates.nix;
  geminiPolicies = import ./helpers/_gemini-policies.nix;
  impeccable = import ./helpers/_impeccable-commands.nix;
  models = import ./helpers/_models.nix;
  agentEnvContent = import ./helpers/_agent-env.nix;
  settingsBuilders = import ./helpers/_settings-builders.nix { inherit cfg config lib; };
  aliasLib = import ./helpers/_aliases.nix {
    inherit lib pkgs;
    scriptsDir = "${config.home.homeDirectory}/${constants.paths.scripts}";
  };
  opencodeProfiles = import ./helpers/_opencode-profiles.nix { inherit config; };
  herdrToml = pkgs.formats.toml { };
  inherit (settingsBuilders)
    geminiSettings
    ompSettings
    opencodeSettingsByProfile
    opencodeAndroidReMcpServers
    opencodeWebReMcpServers
    ;

  opencodeProfileNames = opencodeProfiles.names;
  opencodeGruvboxDarkTheme = toJSON (
    import ./helpers/_opencode-gruvbox-theme.nix { inherit (constants) color; }
  );
  herdrSource = inputs.herdr.outPath;
  herdrConfigFile = herdrToml.generate "herdr-config.toml" {
    onboarding = false;

    terminal = {
      default_shell = "${pkgs.zsh}/bin/zsh";
      new_cwd = "follow";
    };

    theme.name = cfg.herdr.theme;

    ui = {
      sidebar_width = 30;
      sidebar_min_width = 20;
      sidebar_max_width = 42;
      mouse_capture = true;
      mouse_scroll_lines = 3;
      confirm_close = true;
      prompt_new_tab_name = true;
      show_agent_labels_on_pane_borders = true;
      agent_panel_scope = "all";
      accent = "cyan";

      toast.delivery = cfg.herdr.toastDelivery;
      sound = {
        enabled = false;
        agents = {
          claude = "on";
          codex = "on";
          gemini = "on";
          open_code = "on";
        };
      };
    };

    worktrees.directory = cfg.herdr.worktreesDirectory;
    advanced.scrollback_limit_bytes = 52428800;

    experimental = {
      allow_nested = false;
      kitty_graphics = false;
      reveal_hidden_cursor_for_cjk_ime = false;
      cjk_ime_agents = [
        "claude"
        "codex"
        "opencode"
        "gemini"
      ];
    };

    keys = {
      switch_workspace = "prefix+shift+1..9";
      focus_agent = "prefix+alt+1..9";
      previous_agent = "prefix+alt+k";
      next_agent = "prefix+alt+j";
      open_worktree = "prefix+shift+o";
      remove_worktree = "prefix+alt+d";

      command = [
        {
          key = "prefix+g";
          type = "pane";
          command = "lazygit";
        }
        {
          key = "prefix+a";
          type = "pane";
          command = "ai-agent-launcher";
        }
        {
          key = "prefix+shift+a";
          type = "pane";
          command = "ai-agent-inventory";
        }
        {
          key = "prefix+shift+l";
          type = "pane";
          command = "ai-agent-dashboard";
        }
      ];
    };
  };

  opencodeConfigFiles = builtins.listToAttrs (
    lib.flatten (
      map (name: [
        {
          name = "${name}/opencode.json";
          value = {
            text = toJSON opencodeSettingsByProfile.${name};
            force = true;
          };
        }
        {
          name = "${name}/tui.json";
          value = {
            text = toJSON {
              theme = constants.themeNames.opencode;
            };
            force = true;
          };
        }
        {
          name = "${name}/themes/${constants.themeNames.opencode}.json";
          value = {
            text = opencodeGruvboxDarkTheme;
            force = true;
          };
        }
      ]) opencodeProfileNames
    )
  );

  opencodeImpeccableCommandFiles =
    if cfg.impeccable.enable then
      builtins.listToAttrs (
        lib.flatten (
          map (
            profile:
            map (cmd: {
              name = "${profile}/commands/${cmd.name}.md";
              value = {
                text = impeccable.mkImpeccableCommandText cmd;
                force = true;
              };
            }) impeccable.impeccableCommandDefs
          ) opencodeProfileNames
        )
      )
    else
      { };

  opencodeHerdrPluginFiles =
    if cfg.herdr.enable then
      builtins.listToAttrs (
        map (profile: {
          name = "${profile}/plugins/herdr-agent-state.js";
          value = {
            source = "${herdrSource}/src/integration/assets/opencode/herdr-agent-state.js";
            force = true;
          };
        }) opencodeProfileNames
      )
    else
      { };

  mkTextFiles =
    prefix: templates:
    builtins.listToAttrs (
      lib.mapAttrsToList (name: text: {
        name = "${prefix}/${name}";
        value = { inherit text; };
      }) templates
    );
in
{
  config = lib.mkIf cfg.enable {
    home.file = lib.mkMerge [
      # === Claude Agent Definitions ===
      (lib.mkIf cfg.claude.enable (mkTextFiles ".claude/agents" fileTemplates.claudeAgents))

      # === agentmemory Bootstrap ===
      (lib.mkIf cfg.agentmemory.enable {
        ".agentmemory/preferences.json" = {
          text = toJSON {
            schemaVersion = 1;
            lastAgent = null;
            lastAgents = [ ];
            lastProvider = null;
            skipSplash = true;
            skipNpxHint = true;
            skipGlobalInstall = true;
            skipConsoleInstall = true;
            firstRunAt = "1970-01-01T00:00:00.000Z";
          };
          force = true;
        };
      })

      # === Aider Configuration (independent of any agent enable gate) ===
      {
        ".aider.conf.yml".text = builtins.toJSON {
          model = models.aider-model;
          editor-model = models.aider-editor;
          auto-commits = false;
          dirty-commits = false;
          attribute-author = false;
          attribute-committer = false;
          dark-mode = true;
          pretty = true;
          stream = true;
          map-tokens = 2048;
          map-refresh = "auto";
          auto-lint = true;
          lint-cmd = "just lint";
          auto-test = false;
          test-cmd = "just check";
          suggest-shell-commands = false;
        };
      }

      # === Gemini Files (Settings, Commands, Policies) ===
      (lib.mkIf cfg.gemini.enable (
        {
          ".gemini/settings.json" = {
            text = toJSON geminiSettings;
            force = true;
          };
        }
        // (mkTextFiles ".gemini/commands" fileTemplates.geminiCommands)
        // (mkTextFiles ".gemini/policies" geminiPolicies)
      ))

      # === oh-my-pi Files (MCP, Config, Models, Agent Definitions) ===
      (lib.mkIf cfg.omp.enable {
        ".omp/agent/mcp.json" = {
          text = toJSON ompSettings;
          force = true;
        };
        ".omp/agent/models.yml" = {
          text = ''
            providers:
              zai:
                baseUrl: https://api.z.ai/api/anthropic
                apiKey: ZAI_API_KEY
                api: anthropic-messages
                authHeader: true
                models:
                  - id: glm-5.1
                    name: GLM-5.1
                    reasoning: true
                    input:
                      - text
                    contextWindow: 200000
                    maxTokens: 32768
                  - id: glm-5-turbo
                    name: GLM-5 Turbo
                    reasoning: false
                    input:
                      - text
                    contextWindow: 128000
                    maxTokens: 16384
          '';
          force = true;
        };
        ".omp/agent/config.yml" = {
          text = ''
            theme:
              dark: ${cfg.omp.theme}
            modelRoles:
              default: ${cfg.omp.defaultModel}
              plan: ${cfg.omp.planModel}
              smol: ${cfg.omp.smolModel}
            defaultThinkingLevel: high
            compaction:
              enabled: true
              reserveTokens: 16384
            skills:
              enabled: true
            task:
              isolation:
                mode: none
          '';
          force = true;
        };
      })
    ];

    xdg.configFile = lib.mkMerge [
      # Runtime model/service config for shell scripts (always available when agents enabled)
      (lib.mkIf cfg.enable {
        "ai-agents/models.sh" = {
          text = agentEnvContent;
          force = true;
        };
        "ai-agents/aliases.sh" = {
          text = aliasLib.generatedBashRegistry;
          force = true;
        };
      })
      # Herdr terminal-native agent multiplexer config
      (lib.mkIf cfg.herdr.enable {
        "herdr/config.toml" = {
          source = herdrConfigFile;
          force = true;
        };
      })
      # Android RE agent-specific MCP server fragment (merged into runtime config by launcher)
      (lib.mkIf cfg.enable {
        "opencode/android-re-mcp-servers.json" = {
          text = toJSON opencodeAndroidReMcpServers;
          force = true;
        };
      })
      # Web RE agent-specific MCP server fragment (merged into runtime config by launcher)
      (lib.mkIf cfg.enable {
        "opencode/web-re-mcp-servers.json" = {
          text = toJSON opencodeWebReMcpServers;
          force = true;
        };
      })
      # OpenCode profile configs
      (lib.mkIf cfg.opencode.enable (
        opencodeConfigFiles // opencodeImpeccableCommandFiles // opencodeHerdrPluginFiles
      ))
    ];
  };
}
