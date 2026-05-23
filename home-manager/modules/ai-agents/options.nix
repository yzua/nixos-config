# Option definitions for programs.aiAgents.

{
  config,
  constants,
  lib,
  optionHelpers,
  ...
}:

let
  inherit (optionHelpers)
    mkTypedOption
    mkStrOption
    mkBoolOption
    mkIntOption
    mkNullableOption
    ;

  # Helpers only used in this module — not shared across other modules.
  mkAttrsOption = default: description: mkTypedOption lib.types.attrs default description;
  mkAttrsOfStrOption =
    default: description: mkTypedOption (lib.types.attrsOf lib.types.str) default description;
  mkStrListOption =
    default: description: mkTypedOption (lib.types.listOf lib.types.str) default description;
  mkLinesOption = default: description: mkTypedOption lib.types.lines default description;
  mkNullOrStrOption =
    default: description: mkTypedOption (lib.types.nullOr lib.types.str) default description;

  # Shared Codex enum types — used by top-level, profiles, and customAgents options.
  codexPersonalityType = lib.types.enum [
    "none"
    "friendly"
    "pragmatic"
  ];
  codexReasoningEffortType = lib.types.enum [
    "none"
    "minimal"
    "low"
    "medium"
    "high"
    "xhigh"
  ];
  codexApprovalPolicyType = lib.types.enum [
    "untrusted"
    "on-failure"
    "on-request"
    "never"
  ];
  codexReasoningEffortNullable = lib.types.nullOr codexReasoningEffortType;
  codexApprovalPolicyNullable = lib.types.nullOr codexApprovalPolicyType;

  # Shared option set for Codex profiles and custom agents.
  mkCodexEntityOpts =
    extraOpts:
    lib.types.submodule {
      options = {
        model = mkNullOrStrOption null "Model override";
        reasoningEffort = lib.mkOption {
          type = codexReasoningEffortNullable;
          default = null;
          description = "Reasoning effort level";
        };
        approvalPolicy = lib.mkOption {
          type = codexApprovalPolicyNullable;
          default = null;
          description = "Command approval policy";
        };
        sandboxMode = mkNullOrStrOption null "Sandbox mode";
        enableSearch = mkBoolOption false "Enable native Codex web search";
        developerInstructions = mkLinesOption "" "Developer instructions";
        extraToml = mkLinesOption "" "Extra TOML content";
      }
      // extraOpts;
    };

  mcpServerType = lib.types.submodule {
    options = {
      enable = mkBoolOption true "Enable this MCP server";
      type = mkTypedOption (lib.types.enum [
        "local"
        "remote"
      ]) "local" "Server type (local stdio or remote HTTP)";
      command = mkStrOption "" "Command to run for local servers";
      args = mkStrListOption [ ] "Arguments for the command";
      url = mkNullOrStrOption null "URL for remote MCP servers";
      headers = mkNullableOption (lib.types.attrsOf lib.types.str) null "Headers for remote MCP servers";
      env = mkAttrsOfStrOption { } "Environment variables for the server";
    };
  };

  mkMcpServersOption = description: {
    type = lib.types.attrsOf mcpServerType;
    default = { };
    inherit description;
  };
in
{
  options.programs.aiAgents = {
    # === Core Options ===
    enable = lib.mkEnableOption "AI coding agents configuration";

    globalInstructions = mkLinesOption "" "Global instructions injected into all AI agents (Claude CLAUDE.md, OpenCode instructions, Codex developer_instructions, Gemini systemInstruction)";

    secrets = {
      zaiApiKeyFile = mkNullOrStrOption "/run/secrets/zai_api_key" "Path to sops-decrypted Z.AI API key file";
      openrouterApiKeyFile = mkNullOrStrOption "/run/secrets/openrouter_api_key" "Path to sops-decrypted OpenRouter API key file";
      context7ApiKeyFile = mkNullOrStrOption "/run/secrets/context7_api_key" "Path to sops-decrypted Context7 API key file";
    };

    skills = lib.mkOption {
      type = lib.types.listOf (
        lib.types.either lib.types.str (
          lib.types.submodule {
            options = {
              repo = lib.mkOption {
                type = lib.types.str;
                description = "GitHub repository (e.g., 'vercel-labs/skills')";
              };
              skill = lib.mkOption {
                type = lib.types.str;
                description = "Individual skill name from the repository";
              };
            };
          }
        )
      );
      default = [ ];
      description = ''
        List of skills to install from skills.sh.
        Use a string for repo-level installs (e.g., "obra/superpowers").
        Use an attrset { repo, skill } for individual skills
        (e.g., { repo = "vercel-labs/skills"; skill = "find-skills"; }).
      '';
      example = [
        "obra/superpowers"
        {
          repo = "vercel-labs/skills";
          skill = "find-skills";
        }
      ];
    };

    omitSkills = mkStrListOption [ ] "Installed skill names to remove after sync (global scope)";

    agencyAgents = {
      enable = mkBoolOption false "Install msitarzewski/agency-agents for Claude and OpenCode";
    };

    impeccable = {
      enable = mkBoolOption false "Install pbakaus/impeccable skills for Claude and OpenCode";
    };

    herdr = {
      enable = mkBoolOption false "Install and configure Herdr terminal-native AI agent multiplexer";
      theme = mkStrOption "terminal" "Herdr built-in theme name";
      toastDelivery = mkTypedOption (lib.types.enum [
        "off"
        "herdr"
        "terminal"
        "system"
      ]) "terminal" "Herdr toast notification delivery mode";
      worktreesDirectory = mkStrOption "${config.xdg.dataHome}/herdr/worktrees" "Directory for Herdr-managed Git worktrees";
      installIntegrations =
        mkTypedOption
          (lib.types.listOf (
            lib.types.enum [
              "claude"
              "codex"
              "opencode"
              "omp"
            ]
          ))
          [
            "claude"
            "codex"
            "opencode"
            "omp"
          ]
          "Herdr direct integrations to install during Home Manager activation";
    };

    agentmemory = {
      enable = mkBoolOption false "Enable shared persistent memory via agentmemory MCP";
      version = mkStrOption "0.9.16" "agentmemory npm package version for the service and MCP shim";
      url = mkStrOption "http://localhost:3111" "Base URL for the local agentmemory server";
      viewerUrl = mkStrOption "http://localhost:3113" "URL for the local agentmemory viewer";
    };

    everythingClaudeCode = {
      enable = mkBoolOption false "Install a curated Everything Claude Code subset for Claude, Codex, and OpenCode";

      claude = {
        enable = mkBoolOption true "Install curated Everything Claude Code assets for Claude Code";
        commands = mkStrListOption [
          "add-language-rules"
          "database-migration"
          "feature-development"
        ] "Claude command files to install from Everything Claude Code";
        installSkillPack = mkBoolOption true "Install the upstream Everything Claude Code Claude skill pack";
      };

      codex = {
        enable = mkBoolOption true "Install curated Everything Claude Code assets for Codex";
        agents = mkStrListOption [
          "docs-researcher"
          "explorer"
          "reviewer"
        ] "Codex agent files to install from Everything Claude Code";
      };

      opencode = {
        enable = mkBoolOption true "Install curated Everything Claude Code assets for OpenCode";
        commands = mkStrListOption [
          "plan"
          "code-review"
          "verify"
          "tdd"
        ] "OpenCode command files to install from Everything Claude Code";
        installInstructions = mkBoolOption true "Install the upstream OpenCode instruction bundle from Everything Claude Code";
      };

    };

    mcpServers = lib.mkOption (mkMcpServersOption "Shared MCP server definitions used by all agents");

    androidReMcpServers = lib.mkOption (
      mkMcpServersOption "MCP servers only loaded for the android-re agent (not shared globally)"
    );

    webReMcpServers = lib.mkOption (mkMcpServersOption "MCP servers only loaded for the web-re agent.");

    logging = {
      enable = lib.mkEnableOption "centralized logging for AI agents";

      directory = mkStrOption "${config.xdg.dataHome}/ai-agents/logs" "Directory for AI agent logs";
      notifyOnError = mkBoolOption true "Send desktop notification on agent errors";
      enableOtel = mkBoolOption false "Enable OpenTelemetry for supported agents";
      otelEndpoint = mkStrOption "http://localhost:${toString constants.ports.otel}" "OpenTelemetry collector endpoint";
      otelExporter = mkStrOption "otlp" "OpenTelemetry exporter type";
      retentionDays = mkIntOption 30 "Days to retain log files";
    };

    # === Claude Options ===
    claude = {
      enable = lib.mkEnableOption "Claude Code configuration";

      model = mkStrOption "opus" "Default model for Claude Code";
      env = mkAttrsOfStrOption { } "Environment variables for Claude Code";
      permissions = mkAttrsOption {
        allow = [ ];
        deny = [ ];
      } "Permission rules for Claude Code";
      hooks = mkAttrsOption { } "Lifecycle hooks for Claude Code";
      extraSettings = mkAttrsOption { } "Additional Claude Code settings";
    };

    # === OpenCode Options ===
    opencode = {
      enable = lib.mkEnableOption "OpenCode configuration";

      model = mkStrOption "opencode/claude-opus-4-7" "Default model for OpenCode";
      plugins = mkStrListOption [ ] "OpenCode plugins to enable";
      providers = mkAttrsOption { } "Provider configurations for OpenCode";
      permission =
        mkTypedOption (lib.types.either lib.types.str lib.types.attrs) { }
          "OpenCode permission policy";
      agent = mkAttrsOption { } "OpenCode agent definitions";
      command = mkAttrsOption { } "OpenCode slash command definitions";
      lsp =
        mkTypedOption (lib.types.either lib.types.bool lib.types.attrs) { }
          "OpenCode LSP server configuration";
      formatter =
        mkTypedOption (lib.types.either lib.types.bool lib.types.attrs) { }
          "OpenCode formatter configuration";
      experimental = mkAttrsOption { } "OpenCode experimental feature flags";
      defaultAgent = mkNullOrStrOption null "Default primary agent for OpenCode";
      enabledProviders = mkStrListOption [ ] "Only enable these OpenCode providers";
      disabledProviders = mkStrListOption [ ] "Disable these auto-loaded OpenCode providers";
      extraSettings = mkAttrsOption { } "Additional OpenCode settings";
    };

    # === Codex Options ===
    codex = {
      enable = lib.mkEnableOption "Codex CLI configuration";

      model = mkStrOption "openai/gpt-5.5" "Default model for Codex";
      sandboxMode = mkStrOption "workspace-write" "Default sandbox mode for Codex";
      # Active only at top-level codex settings.
      enableSearch = mkBoolOption false "Enable native Codex web search by default";

      personality = lib.mkOption {
        type = codexPersonalityType;
        default = "pragmatic";
        description = "Model personality";
      };

      reasoningEffort = lib.mkOption {
        type = codexReasoningEffortType;
        default = "medium";
        description = "Reasoning effort level";
      };

      approvalPolicy = lib.mkOption {
        type = codexApprovalPolicyType;
        default = "on-request";
        description = "Command approval policy";
      };

      trustedProjects = mkStrListOption [ ] "Paths to projects with trust_level = trusted";

      features = mkTypedOption (lib.types.attrsOf lib.types.bool) { } "Feature flags for Codex";

      profiles = mkTypedOption (lib.types.attrsOf (mkCodexEntityOpts {
        personality = lib.mkOption {
          type = lib.types.nullOr codexPersonalityType;
          default = null;
          description = "Profile-specific personality override";
        };
      })) { } "Named Codex config profiles";

      customAgents = mkTypedOption (lib.types.attrsOf (mkCodexEntityOpts {
        description = mkStrOption "" "Human-facing description for when to use this custom Codex agent";
      })) { } "Custom Codex agents written to ~/.codex/agents/*.toml";

      extraToml = mkLinesOption "" "Extra TOML lines appended to config.toml";
    };

    # === Gemini Options ===
    gemini = {
      enable = lib.mkEnableOption "Gemini CLI configuration";

      theme = mkStrOption "Default" "Theme for Gemini CLI";
      sandboxMode = mkStrOption "cautious" "Sandbox mode (none, cautious, strict)";
      extraSettings = mkAttrsOption { } "Additional Gemini CLI settings";
    };

    # === oh-my-pi Options ===
    omp = {
      enable = lib.mkEnableOption "oh-my-pi AI coding agent configuration";

      defaultModel = mkStrOption "zai/glm-5.1" "Default model for oh-my-pi";
      planModel = mkStrOption "zai/glm-5.1" "Model for planning tasks";
      smolModel = mkStrOption "zai/glm-5-turbo" "Lightweight model for simple tasks";
      theme = mkStrOption "gruvbox-dark" "Theme for oh-my-pi";
      extraSettings = mkAttrsOption { } "Additional oh-my-pi settings merged into mcp.json";
    };

    # === Computed Shell Environment ===
    # Read-only: consumed by terminal/zsh/functions.nix instead of direct file imports.
    shellEnv = {
      zaiInlinePrefix = mkStrOption "" "Computed ZAI env var prefix for claude_glm shell function";
      opencodeProfileData =
        mkTypedOption (lib.types.listOf lib.types.attrs) [ ]
          "Computed OpenCode profile definitions for shell wrapper functions";
    };
  };
}
