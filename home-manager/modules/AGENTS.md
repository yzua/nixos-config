# Home Manager Modules

User-level configuration: programs, dotfiles, theming, desktop environment.
Most modules directly configure `programs.*`, `services.*`, `home.*`; `ai-agents/` is the exception and defines `programs.aiAgents.*` options.

---

## Module Hierarchy

```
modules/
├── ai-agents/          # AI coding agent config (Claude Code, OpenCode, Codex, Antigravity CLI)
│   ├── default.nix     # Import hub (options, activation, files, services, config)
│   ├── options.nix     # All programs.aiAgents option definitions
│   ├── files.nix       # home.file + xdg.configFile declarations
│   ├── packages.nix    # Packages, zsh aliases, systemd user services/timers, log analysis
│   ├── helpers/        # Shared logic (not modules, imported by others)
│   │   ├── _settings-builders.nix # Per-agent settings + profile variant overrides
│   │   ├── _mcp-transforms.nix    # Unified MCP abstraction (shared → agent-specific)
│   │   ├── _opencode-profiles.nix # OpenCode profile names and config paths
│   │   ├── _aliases.nix           # Zsh alias generation for agent launchers/workflows
│   │   ├── _destructive-rules.nix # Destructive action allow/deny rules per agent
│   │   ├── _file-templates.nix    # Config file templates
│   │   ├── _gemini-policies.nix   # Retired Gemini CLI safety policy helper
│   │   ├── _workflow-prompts.nix  # Workflow prompt definitions
│   │   ├── _zai-services.nix      # Z.AI MCP service registry
│   │   ├── _zai-filters.nix       # Z.AI MCP jq filter generation
│   │   ├── _zai-config.nix        # Z.AI API root, timeout, model identifiers
│   │   ├── _mk-cli-autoupdate-script.nix # CLI autoupdate script builder
│   │   ├── _services-shell-aliases.nix  # Shell alias definitions for agent services
│   │   ├── _services-systemd.nix        # Systemd user service/timer definitions
│   │   ├── _formatters.nix       # Formatter registry for auto-formatting hooks
│   │   ├── _impeccable-commands.nix # Impeccable slash command definitions
│   │   ├── _models.nix           # Shared model/provider constants (names, aliases)
│   │   ├── _opencode-gruvbox-theme.nix # OpenCode Gruvbox Dark TUI theme
│   │   ├── _agent-env.nix       # Agent environment variable bridging
│   │   ├── _zai-env.nix         # Z.AI provider env vars (shared by claude_glm + Android RE launchers)
│   │   ├── _git-clone-update.nix # Git clone/update helper for plugin repos
│   │   └── workflows/  # Workflow prompt Nix expressions (9 files)
│   ├── activation/     # Home Manager activation scripts
│   │   ├── default.nix      # Aggregation hub
│   │   ├── secrets.nix      # Secret patching (placeholder → real key injection)
│   │   ├── claude-setup.nix # Claude Code config file writes
│   │   ├── codex-setup.nix  # Codex CLI config file writes
│   │   ├── plugins.nix      # Plugin aggregation (impeccable, agency-agents, ECC)
│   │   ├── _plugin-impeccable.nix # Impeccable skill install
│   │   ├── _plugin-agency-agents.nix # Agency agents install
│   │   ├── _plugin-everything-claude-code.nix # ECC skill install
│   │   ├── _cleanup-agency-agents.nix # Agency agents cleanup on disable
│   │   ├── _cleanup-everything-claude-code.nix # ECC cleanup on disable
│   │   ├── skills.nix       # Skill installations and omissions
│   ├── android-re/     # Android RE workflow prompts and config
│   │   ├── _launchers.nix # Android RE emulator/script launchers (not a module, imported by packages)
│   │   ├── _prompt.nix # Prompt templates (not a module, imported by services)
│   │   └── prompts/    # RE prompt docs (AGENTS.md, README, TOOLS, WORKFLOW, TROUBLESHOOTING)
│   ├── web-re/         # Web RE workflow prompts and config
│   │   ├── _launchers.nix # Web RE launchers (not a module, imported by packages)
│   │   ├── _prompt.nix # Prompt templates (not a module, imported by services)
│   │   └── prompts/    # RE prompt docs (AGENTS.md, README, TOOLS, WORKFLOW, TROUBLESHOOTING)
│   └── config/         # Split configuration values
│       ├── default.nix      # Import hub (defaults, mcp-servers, models, claude)
│       ├── defaults.nix     # Default values for agent options
│       ├── global-instructions.md # Global instructions text (not a module)
│       ├── _skills.nix      # Skill installations and omissions (not a module)
│       ├── mcp-servers.nix  # MCP server definitions + logging
│       ├── mcp-servers-android-re.nix # Android RE MCP server definitions
│       ├── mcp-servers-web-re.nix # Web RE MCP server definitions
│       ├── claude/          # Claude Code configuration
│       │   ├── default.nix  # Permissions, hooks, settings (import hub)
│       │   ├── _hooks.nix   # Lifecycle hooks aggregation (imports helpers + per-stage modules)
│       │   ├── _hooks-helpers.nix # Shared hook constructors (mkFormatterHook, mkBashHook, etc.)
│       │   ├── _hooks-pre-tool-use.nix  # Pre-tool-use safety hooks
│       │   ├── _hooks-post-tool-use.nix # Post-tool-use auto-format hooks
│       │   ├── _hooks-session.nix      # Session lifecycle hooks
│       │   └── _permission-rules.nix # Claude allow/deny rules (not a module)
│       └── models/            # Model/provider registries
│           ├── default.nix  # Import hub + shared toggles (agencyAgents, impeccable)
│           ├── codex.nix    # Codex CLI config (model, profiles, custom agents, developer instructions)
│           ├── opencode.nix # OpenCode config (agents, LSP, providers)
│           ├── _opencode-agents.nix # OpenCode agent definitions
│           ├── _opencode-commands.nix # OpenCode slash command definitions
│           ├── _opencode-android-re.nix # OpenCode Android RE agent definition
│           ├── _opencode-web-re.nix # OpenCode Web RE agent definition
│           ├── _opencode-lsp.nix # OpenCode LSP tool configuration
│           └── omp.nix       # OMP CLI configuration
├── apps/               # App configs (OBS, Syncthing, KeePassXC, Discord, ActivityWatch, browsers, desktop entries)
│   ├── activitywatch.nix # ActivityWatch app usage tracking (Wayland)
│   ├── chromium.nix    # Chromium launch wrapper with Wayland crash workaround
│   ├── desktop-entries.nix # Desktop launchers/wrappers
│   ├── keepassxc.nix   # KeePassXC desktop entry
│   ├── nautilus.nix    # Nautilus (GNOME Files) dconf preferences
│   ├── nixcord.nix     # Discord (Vesktop + Vencord) declarative config
│   ├── obs.nix         # OBS Studio with CUDA and plugins
│   ├── obsidian.nix    # Obsidian Markdown notes app defaults
│   ├── opensnitch-ui.nix # OpenSnitch application firewall GUI
│   ├── metadata-scrubber.nix # Automatic metadata scrubbing (mat2/exiftool)
│   ├── syncthing.nix   # Syncthing local file sync
│   ├── _desktop-local-bin-wrappers.nix # Desktop local bin wrappers (helper, not in default.nix)
│   ├── _mk-wayland-browser-wrapper.nix # Shared Wayland browser wrapper (helper, not in default.nix)
│   ├── vscode/         # VS Code editor
│   │   ├── default.nix      # Import hub (enable, package, mutableExtensionsDir)
│   │   ├── extensions.nix   # Extensions (nixpkgs + marketplace)
│   │   ├── _settings.nix    # Settings builder (not a module, imported by activation)
│   │   ├── _builtin-extensions.nix # Built-in extension list (helper)
│   │   ├── _marketplace-refs.nix # Marketplace extension references (helper)
│   │   └── activation.nix   # Writes mutable settings.json
│   ├── brave/          # Brave browser
│   │   ├── default.nix      # Import hub
│   │   └── extensions.nix   # Declarative extension groups (privacy, dev tools, YouTube/social)
│   └── librewolf/      # LibreWolf browser (multi-profile SOCKS5 proxy)
│       ├── default.nix      # Import hub: programs.librewolf with policies + profiles
│       ├── _profiles.nix    # Profile definitions (not a module, imported by desktop-entries.nix)
│       └── _extensions.nix  # Extension declarations (not a module, imported by default.nix)
├── niri/               # Niri compositor (scrollable tiling Wayland)
│   ├── default.nix     # Import hub
│   ├── main.nix        # Compositor settings (autostart, workspaces, environment, animations)
│   ├── binds.nix       # Keybindings and custom scripts
│   ├── _workspace-names.nix # Workspace display names (not a module, imported by main/binds/rules)
│   ├── _noctalia.nix   # Noctalia Shell IPC helper with auto-start + retry (not a module, imported by binds/idle)
│   ├── input.nix       # Input devices (keyboard, mouse, touchpad, trackpoint)
│   ├── layout.nix      # Layout settings (columns, gaps, focus ring, border)
│   ├── rules.nix       # Window rules (opacity, rounding, floating, workspace assignments)
│   ├── idle.nix        # Idle management (DPMS, lock)
│   ├── lock.nix        # Screen locker
│   └── scripts/        # Extracted helper scripts
│       ├── color-picker.nix  # Wayland color picker (grim + slurp + imagemagick)
│       ├── open-books.nix    # Book launcher (find + wofi + zathura)
│       └── screenshot.nix    # Screenshot annotator (grim + slurp + swappy)
├── noctalia/           # Noctalia Shell (bar, launcher, notifications, wallpaper, OSD, GruvboxAlt colorscheme)
│   ├── default.nix     # Import hub, status-notifier-watcher (SNI protocol)
│   ├── activation.nix  # Activation script (wallpaper deployment, plugin compilation)
│   ├── bar.nix         # Bar widgets (left, center, right panels)
│   ├── settings.nix    # Shell settings (theme, dock, wallpaper, OSD, control center, lock command, hooks)
│   ├── _colorscheme.nix # GruvboxAlt colorscheme generator (produces JSON at activation)
│   ├── _plugins.nix    # Plugin registry and configuration
│   └── plugins/        # Noctalia shell plugins
│       ├── browser-launcher/  # Browser profile launcher (QML)
│       ├── keybind-cheatsheet/ # Keyboard shortcut overlay (QML)
│       ├── mawaqit/           # Prayer time widget (QML)
│       ├── model-usage/       # AI model usage tracker (QML)
├── neovim/             # Neovim editor with LSP, completion, and modern plugins
│   ├── default.nix     # Plugin declarations, treesitter, Lua config loading
│   ├── lua/            # Lua configuration (options, keymaps, LSP, plugins)
│   └── plugins/        # Plugin-specific configs (wakatime)
├── programming-languages/ # Language tooling (Go, JS, Python, Mise)
│   ├── go/              # Go runtime, aliases, GOPATH/GOBIN/session settings
│   │   └── default.nix
│   ├── javascript/      # Node/Bun/Deno toolchain, JS/TS aliases, Playwright wrapper
│   │   ├── default.nix
│   │   └── _gitignores.nix # Git ignore patterns (helper)
│   ├── python/          # Python toolchain, uv/poetry aliases, REPL config
│   │   ├── default.nix
│   │   └── _gitignores.nix # Git ignore patterns (helper)
│   └── mise/            # Mise polyglot runtime manager
│       └── default.nix
├── terminal/           # Shell, terminal, and CLI tools
│   ├── ghostty.nix     # Ghostty terminal emulator
│   ├── zellij/         # Terminal multiplexer (WASM plugins, 4 layouts)
│   │   ├── default.nix # Import hub
│   │   ├── config.nix  # Keybinds, UI, behavior
│   │   ├── layouts.nix # Layouts (default, dev, ai, monitoring)
│   │   └── plugins.nix # WASM plugins (zjstatus, autolock, monocle, room, harpoon, forgot, multitask)
│   ├── direnv.nix      # Per-directory environments
│   ├── scripts.nix     # Custom utility script wrappers (currently `nvidia-fans`)
│   ├── shell.nix       # Nix shell integration and dev tools
│   ├── zsh/            # Zsh + Oh My Zsh (Starship handles the prompt)
│   │   ├── default.nix # Main zsh config with setOptions, OMZ
│   │   ├── aliases.nix # Shell aliases
│   │   ├── config.nix  # Zsh settings and initialization
│   │   ├── functions.nix # Custom zsh functions (nix helpers, agent wrappers, aip)
│   │   └── local-vars.nix # Local shell variables
│   └── tools/          # CLI tools (atuin, bat, btop, cava, carapace, eza, fzf, gh, git, lazygit, mpv, starship, yazi, zathura, zoxide — 15 entries)
│       └── git/        # Git (identity from constants, GPG signing, aliases, hooks)
│           ├── default.nix # Import hub
│           ├── config.nix  # Git settings, aliases, includes
│           └── hooks.nix   # Global hooks (secret scanning, conventional commits, GPG)
├── gpg.nix             # GPG agent and keys
├── ssh.nix             # SSH client hardening
├── mime.nix            # Default app associations
├── qt.nix              # Qt theming (Kvantum + Gruvbox)
├── telemetry.nix       # Telemetry and tracking opt-out variables
└── stylix.nix          # Theming engine (Gruvbox)
```

---

## Package Chunks (`../packages/`)

Packages live separately from modules. Each chunk is a Home Manager module:

```nix
{ pkgs, ... }:
{
  home.packages = [ ... ];
}
```

9 domain chunks + 5 custom chunks + 1 helper: `applications`, `cli`, `development`, `lsp-servers`, `networking`, `niri`, `privacy`, `system-monitoring`, `utilities`, plus `custom/beads`, `custom/chrome-devtools`, `custom/cursor`, `custom/kiro`, `custom/prayer`, and `../_helpers/_egl-wrap.nix` (helper, imported manually).

**When adding packages**: pick the domain chunk, add to its list. Don't create new chunks unless new domain.

---

## Theming (Stylix)

- Base16 scheme: `gruvbox-dark-soft`
- Fonts: JetBrains Mono (mono), Noto Sans (sans), Noto Serif (serif)
- Cursor: Bibata-Modern-Classic (24px)
- Icons: Gruvbox-Plus-Dark
- GTK extra CSS: flat style — `border-radius: 0; box-shadow: none` on `*` selector

### Stylix-Exempt Modules

Stylix has `autoEnable = false` — individual targets must be explicitly opted in. Currently enabled: ghostty, gtk, neovim, zellij.

- Noctalia Shell manages its own theming (not in the Stylix target list).

When adding a new program: add it to the explicit target list in `stylix.nix` if theming is desired. Skip if the program handles its own styling.

---

## Configuration Patterns

### Program Config (most common)

```nix
programs.<tool> = {
  enable = true;
  settings = { ... };
};
```

### Service Config

```nix
services.<service> = {
  enable = true;
  settings = { ... };
};
```

### Home Files (dotfiles)

```nix
home.file.".config/app/config" = {
  text = ''...'';  # or source = ./path;
};
xdg.configFile."app/style.css".text = ''...'';
```

---

## Adding a New Module

1. Create `home-manager/modules/<name>.nix`
2. Add import with comment to `home-manager/modules/default.nix`
3. Use `programs.*` or `services.*` — do NOT define custom options
4. Run: `just modules && just pkgs && just lint && just format && just check && just home`

For subdirectory modules (e.g., new tool in `terminal/tools/`):

1. Create the `.nix` file in the subdirectory
2. Add import to that subdirectory's `default.nix`
3. Same validation pipeline

---

## Sub-directory AGENTS.md

More detailed module-level guidance exists at:

- `ai-agents/AGENTS.md` — Multi-agent architecture, profile variants, activation, hooks
- `neovim/AGENTS.md` — Neovim module boundaries, Lua/plugin wiring patterns
- `terminal/AGENTS.md` — Shell, multiplexer, CLI tools, one-per-tool pattern
- `terminal/zsh/AGENTS.md` — Zsh + OMZ, aliases, agent wrappers, privacy history
- `terminal/tools/AGENTS.md` — CLI tools (atuin, bat, fzf, gh, git, lazygit, yazi, etc.)
- `niri/AGENTS.md` — Compositor keybindings, workspaces, window rules
- `noctalia/AGENTS.md` — Noctalia Shell bar, settings, Stylix-exempt theming
- `apps/AGENTS.md` — Application configs, subdirectory modules (VS Code, Brave)
- `programming-languages/AGENTS.md` — Language toolchains (Go, JS/TS, Python, Mise)

Read these when working in those areas.

---

## Notes

- `home.nix` receives `{ inputs, homeStateVersion, user, pkgsStable, constants, optionHelpers, secretLoader, hmSystemdHelpers, hostname }` via `extraSpecialArgs` from flake
- `hostname` available for host-specific HM config
- `constants` available from `shared/constants.nix` (terminal, editor, font, theme, keyboard, user identity)
- Git identity (name, email, signingKey, githubEmail) lives in `constants.user.*` — used by `terminal/tools/git/config.nix`
- HM modules are usually direct `programs.*`/`services.*` configs; only `programs.aiAgents.*` defines custom HM options
