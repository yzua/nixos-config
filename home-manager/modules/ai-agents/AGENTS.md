# AI Agents Infrastructure

High-density orchestration for Claude Code, OpenCode, Codex CLI, and Antigravity CLI. This module manages dynamic provider switching and secure secret injection.

---

## OVERVIEW

This module centralizes AI agent behavior across multiple CLI tools. It implements a layered configuration system that translates high-level Nix options into tool-specific JSON/TOML formats, enriched with lifecycle hooks and shared MCP capabilities.

---

## ARCHITECTURE

The system follows a strict unidirectional flow:

1. **Options** (`options.nix`): Defines the `programs.aiAgents.*` namespace.
2. **Config Hub** (`config/`): Domain-specific values for models, prompts, and permissions.
3. **Helpers** (`helpers/`): Shared logic imported by config, activation, and files modules.
4. **File Generation** (`files.nix`): Declares configuration files in XDG paths.
5. **Activation Logic** (`activation/`): Handles late-stage secret injection, config setup, best-effort skill management, and state caching.
6. **Services** (`packages.nix`): Packages, zsh aliases, systemd user services/timers, and log analysis tools.

### Profile-Driven Polymorphism

Profiles switch the primary model across all OpenCode config directories. Each profile re-maps the model field via `helpers/_settings-builders.nix`, allowing instant provider migration with zero configuration redundancy.

Seven OpenCode profiles are defined in `helpers/_opencode-profiles.nix`:

| Profile Directory     | Provider/Model                                    |
| --------------------- | ------------------------------------------------- |
| `opencode`            | Default (from `programs.aiAgents.opencode.model`) |
| `opencode-glm`        | Z.AI GLM-5.1                                      |
| `opencode-gemini`     | Google Gemini 3 Pro Preview                       |
| `opencode-gpt`        | OpenAI GPT-5.4                                    |
| `opencode-openrouter` | OpenRouter Hunter Alpha                           |
| `opencode-sonnet`     | Anthropic Claude Sonnet 4.6                       |
| `opencode-zen`        | MiniMax M2.5 Free                                 |

---

## DIRECTORY STRUCTURE

```
ai-agents/
├── default.nix              # Import hub (options, activation, files, services, config)
├── options.nix              # All programs.aiAgents option definitions
├── files.nix                # home.file + xdg.configFile declarations
├── packages.nix             # Packages, zsh aliases, systemd user services/timers, log analysis
├── helpers/                 # Shared logic (not modules, imported by others)
│   ├── _settings-builders.nix   # Per-agent settings + profile variant overrides
│   ├── _mcp-transforms.nix      # Unified MCP abstraction (shared → agent-specific schemas)
│   ├── _opencode-profiles.nix   # OpenCode profile names and config paths
│   ├── _aliases.nix             # Zsh alias generation for agent launchers/workflows
│   ├── _destructive-rules.nix   # Destructive action allow/deny rules per agent
│   ├── _file-templates.nix      # Config file templates
│   ├── _gemini-policies.nix     # Retired Gemini CLI safety policy helper
│   ├── _workflow-prompts.nix    # Workflow prompt definitions
│   ├── _zai-services.nix        # Z.AI MCP service registry
│   ├── _zai-filters.nix         # Z.AI MCP jq filter generation
│   ├── _zai-config.nix          # Z.AI API root, timeout, model identifiers
│   ├── _mk-cli-autoupdate-script.nix     # CLI autoupdate script builder
│   ├── _services-shell-aliases.nix       # Shell alias definitions for agent services
│   ├── _services-systemd.nix             # Systemd user service/timer definitions
│   ├── _formatters.nix                   # Formatter registry for agent hooks
│   ├── _impeccable-commands.nix          # Impeccable skill command definitions and text renderer
│   ├── _models.nix                       # Shared model/provider constants (names, aliases)
│   ├── _opencode-gruvbox-theme.nix       # OpenCode Gruvbox Dark TUI theme
│   ├── _agent-env.nix                    # Agent environment variable bridging
│   ├── _zai-env.nix                      # Z.AI provider env vars (shared by claude_glm + Android RE launchers)
│   ├── _git-clone-update.nix             # Git clone/update helper for plugin repos
│   └── workflows/             # Workflow prompt definitions (Nix expressions)
│       ├── _shared.nix                  # Shared workflow helpers
│       ├── _bugfix-root-cause.nix       # Bugfix root-cause workflow
│       ├── _build-performance.nix       # Build performance workflow
│       ├── _commit-split.nix            # Commit splitting workflow
│       ├── _dependency-upgrade.nix      # Dependency upgrade workflow
│       ├── _markdown-sync.nix           # Markdown sync workflow
│       ├── _refactor-maintainability.nix # Refactor maintainability workflow
│       ├── _runtime-performance.nix     # Runtime performance workflow
│       └── _security-audit.nix          # Security audit workflow
├── activation/              # Home Manager activation scripts
│   ├── default.nix          # Aggregation: wires all activation steps
│   ├── secrets.nix          # Secret patching (placeholder → real key injection)
│   ├── claude-setup.nix     # Claude Code config file writes
│   ├── codex-setup.nix      # Codex CLI config file writes
│   ├── plugins.nix          # Plugin aggregation (impeccable, agency-agents, ECC)
│   ├── _plugin-impeccable.nix # Impeccable skill install
│   ├── _plugin-agency-agents.nix # Agency agents install
│   ├── _plugin-everything-claude-code.nix # ECC skill install
│   ├── _cleanup-agency-agents.nix # Agency agents cleanup on disable
│   ├── _cleanup-everything-claude-code.nix # ECC cleanup on disable
│   ├── skills.nix           # Skill installations and omissions
├── android-re/              # Android RE workflow prompts and config
│   ├── _launchers.nix       # Android RE emulator/script launchers (not a module, imported by packages)
│   ├── _prompt.nix          # Prompt templates (not a module, imported by services)
│   └── prompts/             # RE session prompts and operator guides
│       ├── AGENTS.md        # Quick rules for RE sessions
│       ├── README.md        # Operator guide and workflow map
│       ├── WORKFLOW.md      # End-to-end RE workflow
│       ├── TOOLS.md         # Installed tools and recommendations
│       ├── TROUBLESHOOTING.md # Known issues and recovery
│       ├── CODEQL-GUIDE.md  # CodeQL query writing guide
│       ├── SEMGREP-GUIDE.md # Semgrep rule authoring guide
│       ├── EXPLOIT-METHODOLOGY.md # Exploit development methodology
│       ├── FINDINGS-PRIORITIZATION.md # Vulnerability severity classification
│       ├── DATAFLOW-VALIDATION.md # Data flow analysis and validation
│       ├── SESSION-MEMORY.md # Session context persistence
│       ├── NATIVE-FUZZING.md # Native binary fuzzing guide
│       └── workflow/        # Workflow-specific prompt fragments
├── web-re/                  # Web RE workflow prompts and config
│   ├── _launchers.nix       # Web RE launchers (not a module, imported by packages)
│   ├── _prompt.nix          # Prompt templates (not a module, imported by services)
│   └── prompts/             # RE session prompts and operator guides
│       ├── AGENTS.md        # Quick rules for RE sessions
│       ├── README.md        # Operator guide and workflow map
│       ├── WORKFLOW.md      # End-to-end RE workflow
│       ├── TOOLS.md         # Installed tools and recommendations
│       ├── TROUBLESHOOTING.md # Known issues and recovery
│       ├── CODEQL-GUIDE.md  # CodeQL query writing guide
│       ├── SEMGREP-GUIDE.md # Semgrep rule authoring guide
│       ├── EXPLOIT-METHODOLOGY.md # Exploit development methodology
│       ├── FINDINGS-PRIORITIZATION.md # Vulnerability severity classification
│       ├── DATAFLOW-VALIDATION.md # Data flow analysis and validation
│       └── SESSION-MEMORY.md # Session context persistence
└── config/                  # Split configuration values
    ├── default.nix          # Import hub
    ├── defaults.nix         # Default values for agent options
    ├── _shell-env.nix       # Computed shell env for external modules (zsh, niri)
    ├── global-instructions.md # Global instructions text (not a module)
    ├── _skills.nix          # Skill installations and omissions
    ├── mcp-servers.nix      # MCP server definitions + logging
    ├── mcp-servers-android-re.nix # Android RE MCP server definitions
    ├── mcp-servers-web-re.nix # Web RE MCP server definitions
    ├── claude/              # Claude Code configuration
    │   ├── default.nix      # Import hub (permissions, hooks, settings)
    │   ├── _hooks.nix       # Lifecycle hooks aggregation (imports helpers + per-stage modules)
    │   ├── _hooks-helpers.nix # Shared hook constructors (mkFormatterHook, mkBashHook, etc.)
    │   ├── _hooks-pre-tool-use.nix  # Pre-tool-use safety hooks
    │   ├── _hooks-post-tool-use.nix # Post-tool-use auto-format hooks
    │   ├── _hooks-session.nix      # Session lifecycle hooks
    │   └── _permission-rules.nix # Claude allow/deny rules
    └── models/              # Model/provider registries
        ├── default.nix      # Import hub + shared toggles (agencyAgents, impeccable)
        ├── codex.nix        # Codex CLI configuration
        ├── opencode.nix      # OpenCode configuration (agents, LSP, providers)
        ├── _opencode-agents.nix # OpenCode agent definitions
        ├── _opencode-commands.nix # OpenCode slash command definitions
        ├── _opencode-android-re.nix # OpenCode Android RE agent definition
        ├── _opencode-web-re.nix # OpenCode Web RE agent definition
        ├── _opencode-lsp.nix # OpenCode LSP tool configuration
        └── omp.nix          # OMP CLI configuration
```

---

## SECRETS

Secure secret injection is handled during the Home Manager activation phase to prevent sensitive keys from entering the Nix store.

1. **Placeholders**: Config files are written with unique placeholders (e.g., `__GITHUB_TOKEN_PLACEHOLDER__`, `__OPENROUTER_API_KEY_PLACEHOLDER__`).
2. **DAG Patching**: The `patchAiAgentSecrets` script runs as a DAG entry after `writeBoundary`.
3. **Injection**: It uses `jq` with walk filters for JSON files, reading keys directly from `/run/secrets/` or `gh` CLI and overwriting the placeholders in-place.

---

## CONVENTIONS

### Unified MCP Abstraction

Never define MCP servers per-agent. Define them once in `programs.aiAgents.mcpServers`. The `helpers/_mcp-transforms.nix` logic automatically generates the correct transport configuration for every supported agent.

### Helper File Rules

All `helpers/_*.nix` files are plain Nix expressions (not modules). They are imported with `import ../helpers/<name>.nix { ... }` by the modules that need them. They are never listed in import hubs.

### Activation File Rules

The `activation/` directory is a submodule with its own `default.nix`. Individual files (`secrets.nix`, `claude-setup.nix`, `codex-setup.nix`, `plugins.nix`, `skills.nix`) are helpers imported by `activation/default.nix` — not listed in the top-level `ai-agents/default.nix` import hub.

### External Module Interface

The `programs.aiAgents.shellEnv` option is the **only** interface external modules should consume from ai-agents. It provides computed shell environment data through the HM option system rather than requiring raw file imports.

- `shellEnv.zaiInlinePrefix`: env var prefix string for `claude_glm` shell function
- `shellEnv.opencodeProfileData`: list of profile attrsets for shell wrapper generation

External modules (currently `terminal/zsh/functions.nix`) read `config.programs.aiAgents.shellEnv.*` instead of importing `helpers/_zai-env.nix` or `helpers/_opencode-profiles.nix` directly. The computed values are set in `config/_shell-env.nix`.

### Complexity Hotspots (WARNING)

This module contains significant **embedded Bash logic** that bypasses standard Nix abstraction for performance and compatibility:

- **`config/claude/_hooks.nix`**: Heavy use of `jq` and `grep` within Claude Code lifecycle hooks for auto-formatting and destructive command detection.
- **`activation/default.nix`**: Complex sequential skill installation/removal logic with state-caching to prevent redundant network calls; skill sync failures are logged as warnings so Home Manager activation can continue. Also handles mirroring Claude skills into `~/.codex/skills` and disabling the shared `~/.agents/skills` tree to prevent OpenCode duplicate-skill spam.

### Validation Pipeline

```bash
just modules   # Validate import tree
just lint      # Run statix/deadnix
just format    # nixfmt-tree
just check     # Full flake evaluation
just home      # Apply configuration
```
