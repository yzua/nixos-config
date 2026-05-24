# AI Agents — Model Configs

Home Manager modules setting default values for `programs.aiAgents.*` options. Each file configures a specific AI agent tool's defaults — model selection, agent definitions, feature flags, themes, hooks, and tool configurations.

Parent: `home-manager/modules/ai-agents/AGENTS.md`

---

## Files

| File                       | Purpose                                                                                     |
| -------------------------- | ------------------------------------------------------------------------------------------- |
| `default.nix`              | Import hub: imports codex, omp, opencode                                                    |
| `codex.nix`                | Codex CLI: model (gpt-5.5), profiles, custom agents, features                               |
| `opencode.nix`             | OpenCode: model (opencode/claude-opus-4-7), 7 agents, 6 commands, LSP, permissions          |
| `omp.nix`                  | OMP CLI: model configuration                                                                |
| `_opencode-agents.nix`     | OpenCode agent definitions (build, plan, review, recon, patch, optimize, android-re)        |
| `_opencode-commands.nix`   | OpenCode slash command definitions (commit-split, refactor, security-audit, etc.)           |
| `_opencode-android-re.nix` | OpenCode Android RE agent definition (imports `../../android-re/_prompt.nix`)               |
| `_opencode-web-re.nix`     | OpenCode Web RE agent definition (imports `../../web-re/_prompt.nix`)                       |
| `_opencode-lsp.nix`        | Plain attrset (not a module): LSP server definitions for 9 languages                        |

---

## Conventions

- All files are proper Home Manager modules except `_opencode-lsp.nix` (plain attrset).
- Model references come from `../../helpers/_models.nix` — never hardcode model strings.
- `extraSettings` pattern for complex nested config that doesn't map to typed options.
- Placeholder pattern for secrets: `__OPENROUTER_API_KEY_PLACEHOLDER__` etc., patched during activation.
- Workflow prompts imported from `../../helpers/_workflow-prompts.nix`.

---

## Gotchas

- `opencode.nix` imports `_opencode-agents.nix`, `_opencode-commands.nix`, and `_opencode-android-re.nix`. The latter imports `../../android-re/_prompt.nix` — creates an indirect dependency on the `android-re/` directory.
- `codex.nix` sets `trustedProjects` to the System directory path from `config.home.homeDirectory`.
- `_opencode-lsp.nix` is the only non-module file — imported directly by `opencode.nix` as the `lsp` option value.

---

## Dependencies

- `../../helpers/_models.nix` (codex, gemini, opencode)
- `../../helpers/_workflow-prompts.nix` (opencode.nix)
- `../../android-re/_prompt.nix` (opencode.nix)
