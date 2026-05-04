# Utility Scripts

Repository Bash scripts across `ai/`, `apps/`, `build/`, `hardware/`, `sops/`, `system/`, and `lib/`. `lib/` contains shared sourced helpers such as `logging.sh` and `test-helpers.sh`. All shell scripts are checked by `just lint`.

---

## Directory Map

```
scripts/
├── ai/
│   ├── _agent-registry.sh   # Shared agent registry: aliases, launcher choices, command mappings, workflow suffixes
│   ├── agent-launcher.sh    # Interactive multi-provider AI agent launcher
│   ├── agent-launcher-test.sh # Unit tests for agent-launcher.sh
│   ├── agent-log-wrapper.sh # Agent command logging wrapper with error split
│   ├── agent-analyze.sh     # Log analyzer CLI (stats/errors/sessions/search/tail/report)
│   ├── agent-dashboard.sh   # fzf dashboard wrapper for analyzer commands
│   ├── agent-inventory.sh   # Interactive fzf inventory for AI tools (skills, MCP, agents)
│   ├── _inventory-collectors.sh # Shared inventory data collectors (sourced by agent-inventory.sh)
│   ├── _inventory-walkers.sh # Generic directory-walking helpers for inventory (sourced by agent-inventory.sh)
│   ├── _inventory-helpers.sh # Shared inventory helper functions (sourced by agent-inventory.sh)
│   ├── agents-search.sh     # Scan project trees for directories needing AGENTS.md
│   ├── agents-search-test.sh # Unit tests for agents-search.sh
│   ├── agent-iter.sh        # Run an AI agent command N times (iterative loop)
│   ├── agent-iter-test.sh   # Unit tests for agent-iter.sh
│   ├── agent-registry-drift-test.sh # Unit tests for agent registry drift detection
│   ├── _findings-schema.sh  # Shared SQLite schema renderer for RE findings databases
│   ├── _findings-common.sh  # Shared SQLite findings CLI implementation for RE adapters
│   ├── _workspace-init-common.sh # Shared workspace scaffold helpers for RE adapters
│   └── android-re/
│       ├── re-avd.sh        # Android emulator management (AVD create/start/snapshot)
│       ├── re-avd-test.sh   # Unit tests for re-avd.sh
│       ├── re-static.sh     # Android static analysis workflow
│       ├── opencode-android-re.sh # OpenCode Android RE workspace launcher
│       ├── frida-spoof-build.js # Frida gadget spoof build script
│       ├── frida-bypass-certificate-pinner.js # Frida: bypass OkHttp CertificatePinner
│       ├── frida-hook-build-fields.js # Frida: log android.os.Build fields
│       ├── frida-hook-crypto.js # Frida: hook crypto operations
│       ├── frida-hook-file-exists.js # Frida: log File.exists root/emulator checks
│       ├── frida-hook-intent.js # Frida: log Intent creation and routing
│       ├── frida-hook-network.js # Frida: log network requests and responses
│       ├── frida-hook-shared-prefs.js # Frida: log SharedPreferences reads/writes
│       ├── frida-hook-url-log.js # Frida: log URL creation and OkHttp requests
│       ├── frida-hook-webview.js # Frida: hook WebView load and JS interface calls
│       ├── frida-hooks-test.sh # Unit tests for Frida hook scripts
│       ├── _helpers.sh      # Shared helpers: adb_prop, emulator_online, resolve_niri_android_workspace
│       ├── _spoof-table.sh  # Device fingerprint spoof table
│       ├── _emulator.sh     # Emulator management helpers
│       ├── _frida.sh        # Frida helper functions
│       ├── _mitm.sh         # mitmproxy helper functions
│       ├── _spoof.sh        # Device spoof helper functions
│       ├── _status.sh       # Status check helper functions
│       ├── _tmux.sh         # tmux helper functions
│       └── workspace-init.sh # Android RE workspace initialization
│   └── web-re/
│       ├── web-re.sh          # Web RE workflow launcher
│       ├── opencode-web-re.sh # OpenCode Web RE workspace launcher
│       ├── findings.sh        # Web RE findings CLI adapter
│       ├── _chrome.sh         # Chrome DevTools helper functions
│       ├── _helpers.sh        # Shared helpers for web RE workflows
│       ├── _mitm.sh           # mitmproxy helper functions
│       ├── _tmux.sh           # tmux helper functions
│       └── workspace-init.sh  # Web RE workspace initialization
├── apps/
│   ├── browser-select.sh    # Browser profile selector (wofi menu)
│   ├── element-desktop-keyring.sh # Element Desktop keyring helper
│   ├── playwright-cli-mcp-wrapper.sh # Playwright CLI local bin wrapper
│   ├── xdg-open-wrapper.sh  # XDG open wrapper for Wayland
│   └── youtube-mpv.sh       # YouTube URL opener via mpv
├── build/
│   ├── modules-check.sh     # Validates default.nix imports match .nix files on disk
│   ├── modules-check-test.sh # Unit tests for modules-check.sh
│   ├── packages-check.sh    # Checks for duplicate packages and program/module conflicts
│   ├── pre-commit-hook.sh   # Git hook: modules-check → statix/deadnix → format check → flake check
│   ├── pre-push-hook.sh     # Git hook: enforces GPG-signed commits
│   └── shellcheck-nix-inline.sh # Lints inline Bash in writeShellScript blocks
├── hardware/
│   └── nvidia-fans.sh       # GPU fan control
├── lib/
│   ├── logging.sh           # Shared logging library (colored output, timestamps)
│   ├── log-dirs.sh          # Log directory path resolution
│   ├── error-patterns.sh    # Shared error keyword pattern for AI agent log analysis
│   ├── test-helpers.sh      # Shared test utilities (assertions, mocking)
│   ├── awk-utils.awk        # Shared AWK helper functions
│   ├── extract-nix-shell.awk # Extract shell snippets from Nix files
│   ├── extract-nix-packages.awk # Extract package names from Nix files
│   ├── fzf-theme.sh         # FZF theme configuration (Gruvbox colors)
│   └── require.sh           # Shared dependency assertion helpers
├── sops/
│   └── sops-edit.sh         # Secrets editor (RAM-backed tmpfs, age encryption)
├── system/
│   └── report/
│       ├── system-report.sh     # Unified health report (full/errors mode)
│       ├── report-collectors.sh # Compatibility shim loading collector modules
│       ├── report-collectors-core.sh # Core collectors: systemd, timers, network, builds, AI logs
│       ├── report-collectors-observability.sh # Observability collectors: Loki/Netdata/Scrutiny/resource metrics
│       ├── report-collectors-security.sh # Security collectors: fail2ban, Lynis, OpenSnitch, hardening
│       ├── report-helpers.sh    # Report generation helper functions
│       └── report-collectors-test.sh # Unit tests for report collectors
```

---

## Conventions

- **Strict Shebang**: `#!/usr/bin/env bash` followed by `set -euo pipefail`. This is mandatory for all executable scripts to ensure portability and immediate exit on errors or unset variables.
- **Sourced libraries** (`lib/`): Do NOT include `set -euo pipefail` (inherited from caller).
- **Quote all variables**: `"$var"`, `"${array[@]}"`.
- **Conditionals**: `[[ ... ]]` (not `[ ... ]`).
- **Arrays**: `mapfile` for reading from commands.
- **Error handling**: `error_exit "message" code`.
- **Logging**: Source `scripts/lib/logging.sh` — never define `log_info`/`print_info` locally.
- **Unit Testing**: Use the `*-test.sh` suffix for test files, placed in the same directory as the script under test. Run tests frequently.

---

## Shared Logging Library (`lib/logging.sh`)

Source the library using:

```bash
source "$(dirname "$0")/../lib/logging.sh"
```

### Functions

- **Colored Output**: `print_info`, `print_success`, `print_warning`, `print_error`. These use emojis and ANSI colors for terminal visibility.
- **Timestamped Logging**: `log_info`, `log_success` (stdout), `log_warning`, `log_error` (stderr). These add ISO-style timestamps.

---

## Complexity Hotspots (Warnings)

- **`ai/agent-launcher.sh`**: Uses a procedural registry (large `case` statements) for agent and workflow selection. When adding new agents, you must update multiple functions (`resolve_workflow_prompt`, `execute_agent`, etc.).
- **`ai/agent-inventory.sh`**: Relies on manual JSON/TOML parsing and directory traversal to build the AI tool inventory. Ensure changes to config locations are reflected here.

---

## Adding a Script

1. Create `scripts/<category>/<name>.sh`.
2. Start with the mandatory `#!/usr/bin/env bash` and `set -euo pipefail`.
3. Source `../lib/logging.sh` for standard logging.
4. Add a unit test file `<name>-test.sh`.
5. If the script is referenced from Nix, use `pkgs.writeShellApplication` in the relevant Nix module to manage runtime dependencies.
6. Run `just lint` to verify with `shellcheck`.

## Nix Integration Table

| Script                                             | Referenced By                                                                                                                        |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `build/modules-check.sh`                           | `justfile` (`just modules`)                                                                                                          |
| `build/packages-check.sh`                          | `justfile` (`just pkgs`)                                                                                                             |
| `build/shellcheck-nix-inline.sh`                   | `justfile` (`just lint`)                                                                                                             |
| `system/report/system-report.sh`                   | `nixos-modules/system-report/_config.nix` (wrapped with `writeShellApplication`)                                                     |
| `system/report/report-collectors.sh`               | Sourced by `system-report.sh` (loads module files)                                                                                   |
| `system/report/report-collectors-core.sh`          | Sourced by `system/report/report-collectors.sh`                                                                                      |
| `system/report/report-collectors-observability.sh` | Sourced by `system/report/report-collectors.sh`                                                                                      |
| `system/report/report-collectors-security.sh`      | Sourced by `system/report/report-collectors.sh`                                                                                      |
| `system/report/report-helpers.sh`                  | Sourced by `system-report.sh`                                                                                                        |
| `ai/agent-launcher.sh`                             | `home-manager/modules/ai-agents/helpers/_aliases.nix` (`ai-agent-launcher` wrapper)                                                  |
| `ai/agent-log-wrapper.sh`                          | `home-manager/modules/ai-agents/packages.nix` (`ai-agent-log-wrapper` wrapper)                                                       |
| `ai/agent-analyze.sh`                              | `home-manager/modules/ai-agents/packages.nix` (`ai-agent-analyze` wrapper)                                                           |
| `ai/agent-dashboard.sh`                            | `home-manager/modules/ai-agents/packages.nix` (`ai-agent-dashboard` wrapper)                                                         |
| `ai/agent-inventory.sh`                            | `home-manager/modules/ai-agents/helpers/_aliases.nix` (`ai-agent-inventory` wrapper)                                                 |
| `ai/agent-iter.sh`                                 | `home-manager/modules/ai-agents/packages.nix` (iterative agent loop wrapper)                                                         |
| `ai/android-re/re-avd.sh`                          | `home-manager/modules/ai-agents/config/models/_opencode-android-re.nix` (prompt docs), called at runtime by `opencode-android-re.sh` |
| `ai/android-re/opencode-android-re.sh`             | `home-manager/modules/ai-agents/android-re/_launchers.nix` (launcher for `oc*are` wrapper binaries)                                  |
| `ai/android-re/re-static.sh`                       | Manual Android RE static-analysis workflow usage                                                                                     |
| `sops/sops-edit.sh`                                | `justfile` (`just sops-edit`)                                                                                                        |
| `apps/browser-select.sh`                           | `home-manager/modules/apps/_desktop-local-bin-wrappers.nix` (`browser-select` wrapper)                                               |
| `apps/element-desktop-keyring.sh`                  | `home-manager/modules/apps/_desktop-local-bin-wrappers.nix` (local bin wrapper)                                                      |
| `apps/playwright-cli-mcp-wrapper.sh`               | `home-manager/modules/programming-languages/javascript/default.nix` (local bin wrapper)                                              |
| `apps/xdg-open-wrapper.sh`                         | `home-manager/modules/apps/_desktop-local-bin-wrappers.nix` (local bin wrapper)                                                      |
| `apps/youtube-mpv.sh`                              | `home-manager/modules/apps/_desktop-local-bin-wrappers.nix` (local bin wrapper)                                                      |
| `hardware/nvidia-fans.sh`                          | `home-manager/modules/terminal/scripts.nix` (`nvidia-fans` wrapper)                                                                  |
