# Web RE Toolkit

Web security testing scripts for launching Chrome with DevTools, managing mitmproxy, and orchestrating web RE sessions.

Parent: `scripts/ai/AGENTS.md`

---

## Files

| File                 | Purpose                                                                          |
| -------------------- | -------------------------------------------------------------------------------- |
| `web-re.sh`          | Main orchestrator: Chrome + mitmproxy + tmux session management                  |
| `workspace-init.sh`  | Target workspace scaffolding with OWASP Web Top 10 2021 templates                |
| `opencode-web-re.sh` | OpenCode session launcher for web RE agent                                       |
| `findings.sh`        | Web schema adapter for the shared SQLite findings CLI                            |
| `_helpers.sh`        | Shared helpers: `chrome_running`, `port_in_use`, `resolve_niri_web_re_workspace` |
| `_chrome.sh`         | Chrome browser management: start/stop/status with remote debugging               |
| `_mitm.sh`           | mitmproxy helper functions (sourced library)                                     |
| `_tmux.sh`           | tmux helper functions (sourced library)                                          |

---

## Conventions

- `_` prefix for sourced libraries (`_helpers.sh`, `_chrome.sh`, `_mitm.sh`, `_tmux.sh`) -- no `set -euo pipefail`.
- Chrome launched with `--remote-debugging-port=9222` and a dedicated user-data-dir at `~/.cache/web-re-tools/chrome-profile/`.
- Environment-variable-driven with sensible defaults (`CHROME_DEBUG_PORT`, `MITM_PORT`, etc.).
- 5-window tmux layout: `shell`, `mitm`, `proxy`, `logs`, `recon`.

---

## Gotchas

- Chrome must be launched with `--no-first-run` to avoid first-run dialogs that block automation.
- `opencode-web-re.sh` reads `WEB_RE_OPENCODE_PROFILE` env var (set by Nix wrapper).
- Niri window rule matches title `^web-re` -- do not change the Ghostty title without updating niri config.
- Runtime tools required: `google-chrome-stable` or `chromium`, `mitmdump`, `nuclei`, `sqlmap`, `nmap`, `curl`, `jq`.
- `findings.sh` keeps the Web-specific `services.url` and `vulns.endpoint` columns; shared command behavior lives in `../_findings-common.sh`.

---

## Dependencies

- `../../lib/logging.sh`, `../../lib/require.sh` (via `_helpers.sh`)
- Nix modules: `ai-agents/web-re/` (wrapper binaries, prompt injection)
- Nix helpers: `ai-agents/web-re/_launchers.nix` wraps `opencode-web-re.sh`
