# AI Agents — Helpers

Shared pure-Nix expression library imported by config, activation, and files modules. Plain functions returning attrsets — NOT Home Manager modules.

Parent: `home-manager/modules/ai-agents/AGENTS.md`

---

## Files

| File                            | Purpose                                                                                          |
| ------------------------------- | ------------------------------------------------------------------------------------------------ |
| `_models.nix`                   | Single source of truth for model identifiers (claude-opus, gpt-default, glm, etc.)               |
| `_mcp-transforms.nix`           | Unified MCP abstraction mapped to agent-specific schemas                                         |
| `_formatters.nix`               | Formatter registry (biome, rustfmt, nixfmt, prettier, etc.)                                      |
| `_settings-builders.nix`        | Per-agent settings builders; imports `_mcp-transforms`, `_formatters`, `_models`                 |
| `_destructive-rules.nix`        | Canonical destructive command list + generators for deny rules                                   |
| `_gemini-policies.nix`          | Gemini CLI TOML safety policies (allow research, deny destructive)                               |
| `_opencode-profiles.nix`        | Seven OpenCode profile names and their XDG config paths                                          |
| `_opencode-gruvbox-theme.nix`   | Gruvbox Dark theme definition for OpenCode TUI                                                   |
| `_aliases.nix`                  | Zsh alias generation for agent launchers and workflow combos                                     |
| `_workflow-prompts.nix`         | Workflow prompt constants (commitSplit, securityAudit, etc.)                                     |
| `_file-templates.nix`           | Static agent/skill/definition templates for Claude and Gemini                                    |
| `_impeccable-commands.nix`      | Impeccable skill pack command definitions and renderer                                           |
| `_services-systemd.nix`         | Systemd user services/timers: log cleanup, DB vacuum, CLI auto-update                            |
| `_services-shell-aliases.nix`   | Shell aliases for logging/analytics (ai-logs, ai-errors, ai-stats)                               |
| `_mk-cli-autoupdate-script.nix` | Generates shell script for auto-updating a CLI binary via bun/npm                                |
| `_zai-services.nix`             | Z.AI MCP service registry: service names, MCP keys, base URL                                     |
| `_zai-filters.nix`              | Agent-specific jq filters for Z.AI MCP secret injection                                          |
| `_git-clone-update.nix`         | Generates Bash snippet for git clone/update under `~/.local/share/`                              |
| `_agent-env.nix`                | Agent environment variable bridging                                                              |
| `_agentmemory-runtime.nix`      | agentmemory runtime dependencies, including the pinned `iii` engine binary                       |
| `_zai-env.nix`                  | Z.AI provider env vars (shared by claude_glm + Android RE launchers)                             |
| `_zai-config.nix`               | Z.AI API root, timeout, model identifiers; imported by `_zai-env`, `_zai-services`, `_agent-env` |
| `workflows/`                    | Workflow prompt Nix expressions (9 files: shared, bugfix, build-perf, commit-split, etc.)        |

---

## Conventions

- All files are plain Nix expressions taking explicit arguments and returning attrsets.
- Underscore-prefixed (`_*.nix`) to distinguish from import-hub modules.
- Never listed in import hubs — imported directly by consumers.
- Single source of truth pattern: `_models.nix` for model IDs, `_destructive-rules.nix` for blocked commands, `_formatters.nix` for tool/formatter mappings.

---

## Gotchas

- `_settings-builders.nix` imports `_mcp-transforms`, `_formatters`, and `_models` — changes propagate here.
- `_zai-filters.nix` imports `_zai-services.nix` directly; both must stay in sync.
- `_gemini-policies.nix` imports `_destructive-rules.nix` directly.
- `_aliases.nix` imports `_models.nix`.
- `_agent-env.nix`, `_zai-env.nix`, and `_zai-services.nix` all import `_zai-config.nix` — changes to the Z.AI API root URL propagate to env vars, launchers, and MCP filters through three paths.
- `toHookPattern` in `_destructive-rules.nix` has special-case regex escaping for `rm -rf /`, `rm -rf ~`, `dd` — consider grep regex safety when adding commands.
