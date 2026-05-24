# AI Agent Orchestration Scripts

AI agent launching, iterating, logging, analyzing, and inventorying across Claude Code, Codex, OpenCode, and Antigravity CLI with a unified alias system and shared workflow suffixes.

Parent: `scripts/AGENTS.md`

---

## Files

| File                           | Purpose                                                                                                   |
| ------------------------------ | --------------------------------------------------------------------------------------------------------- |
| `_agent-registry.sh`           | Single source of truth for all agent aliases, launcher choices, workflow suffixes, ZAI key resolution     |
| `agent-launcher.sh`            | Interactive fzf-based multi-provider AI agent launcher                                                    |
| `agent-launcher-test.sh`       | Unit tests for agent-launcher.sh                                                                          |
| `agent-log-wrapper.sh`         | Timestamped log splitting (stdout `.log`, stderr `-errors.log`), optional desktop notification on failure |
| `agent-analyze.sh`             | CLI log analyzer: stats, errors, sessions, search, tail, report, patterns                                 |
| `agent-dashboard.sh`           | fzf-driven interactive dashboard looping over analyzer commands                                           |
| `agent-inventory.sh`           | Dynamic inventory browser for AI tools (profiles, models, MCP, hooks, skills, agents)                     |
| `_inventory-collectors.sh`     | Shared inventory data collectors (sourced by agent-inventory.sh)                                          |
| `_inventory-walkers.sh`        | Generic directory-walking helpers for inventory (sourced by agent-inventory.sh)                           |
| `_inventory-helpers.sh`        | Shared inventory helper functions (sourced by agent-inventory.sh)                                         |
| `agents-search.sh`             | Scans project trees for directories needing AGENTS.md                                                     |
| `agents-search-test.sh`        | Unit tests for agents-search.sh                                                                           |
| `agent-iter.sh`                | Headless iterative agent runner with rate-limit retry                                                     |
| `agent-iter-test.sh`           | Unit tests for agent-iter.sh                                                                              |
| `agent-registry-drift-test.sh` | Unit tests for agent registry drift detection                                                             |
| `_findings-schema.sh`          | Shared SQLite schema renderer for RE findings databases                                                   |
| `_findings-common.sh`          | Shared SQLite findings CLI implementation sourced by Web/Android RE adapters                              |
| `_workspace-init-common.sh`    | Shared workspace scaffold helpers sourced by Web/Android RE workspace initializers                        |
| `android-re/`                  | Android RE toolkit (see `android-re/AGENTS.md`)                                                           |

---

## Conventions

- `_agent-registry.sh` is the single source of truth — both `agent-launcher.sh` (interactive) and `agent-iter.sh` (headless) source it.
- `LAUNCHER_SIMPLE_ALIASES` owns the simple-mode picker list; keep every listed alias registered in `AGENT_REGISTRY`.
- Two registries: `AGENT_REGISTRY` (interactive with `--dangerously-skip-permissions` etc.) and `AGENT_ITER_REGISTRY` (headless `--print`/`exec`/`run`).
- Workflow suffixes (`cm`, `rf`, `fx`, `sa`, `du`, `bp`, `rp`, `md`) are appended to base aliases (e.g., `clglmcm` = Claude GLM + commit-split).
- fzf is mandatory for interactive scripts. All use shared `fzf-theme.sh` from `../lib/`.
- Test files use `AI_AGENT_LAUNCHER_SOURCE_ONLY=1` to source scripts without executing `main()`.

---

## Gotchas

- `_agent-registry.sh` must be sourced AFTER `logging.sh` (it calls logging functions).
- `_findings-common.sh` must be sourced only after domain adapters define their schema/projection variables.
- `_agent-registry.sh` does NOT have `set -euo pipefail` — it is a sourced library.
- `AGENT_ITER_REGISTRY` uses `SC2034` suppression because it is consumed by `agent-iter.sh`, not by the registry file itself.
- Workflow suffix env vars (`COMMIT_SPLIT_PROMPT`, etc.) are set externally by Nix wrappers or shell env, not defined here.
- `agent-iter.sh` rejects interactive-only aliases (like plain `cl`) without a prompt — headless-only.
- ZAI API key for Claude GLM variants is resolved from `/run/secrets/zai_api_key`.

---

## Dependencies

- `../lib/logging.sh`, `../lib/log-dirs.sh`, `../lib/fzf-theme.sh`, `../lib/error-patterns.sh`, `../lib/test-helpers.sh`
- `_findings-schema.sh` for Web/Android RE findings database schemas
- `_findings-common.sh` for Web/Android RE findings CLI behavior
- `_workspace-init-common.sh` for Web/Android RE workspace scaffold mechanics
- Nix wrappers in `home-manager/modules/ai-agents/` wrap several scripts via `writeShellApplication`
