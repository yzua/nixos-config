# Android RE Toolkit

Automated emulator environment setup (rooted AVD with Frida, mitmproxy, device spoofing), Frida instrumentation hooks for runtime analysis, static analysis tooling, and OpenCode workspace integration.

Parent: `scripts/ai/AGENTS.md`

---

## Files

| File                                 | Purpose                                                                                                  |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `re-avd.sh`                          | Main environment manager: 10-phase start sequence (cleanup, boot, proxy, root, spoof, CA, Frida, health) |
| `re-avd-test.sh`                     | Unit tests for re-avd.sh                                                                                 |
| `re-static.sh`                       | Static analysis: `prepare` (apktool+jadx), `hashes`, `inventory`                                         |
| `opencode-android-re.sh`             | OpenCode session launcher (called by `oc*are` wrappers)                                                  |
| `findings.sh`                        | Android schema adapter for the shared SQLite findings CLI                                                |
| `_helpers.sh`                        | Shared helpers: `adb_prop`, `emulator_online`, `resolve_niri_android_workspace`                          |
| `_spoof-table.sh`                    | Declarative Pixel 7 spoof: 40+ system properties, 8 files to hide, 6 services to stop                    |
| `_emulator.sh`                       | Emulator management helpers (sourced library)                                                            |
| `_frida.sh`                          | Frida helper functions (sourced library)                                                                 |
| `_mitm.sh`                           | mitmproxy helper functions (sourced library)                                                             |
| `_spoof.sh`                          | Device spoof helper functions (sourced library)                                                          |
| `_status.sh`                         | Status check helper functions (sourced library)                                                          |
| `_tmux.sh`                           | tmux helper functions (sourced library)                                                                  |
| `frida-spoof-build.js`               | Frida gadget: overrides Build fields to Pixel 7, hides emulator files                                    |
| `frida-bypass-certificate-pinner.js` | Frida: bypasses OkHttp CertificatePinner + Conscrypt TrustManagerImpl                                    |
| `frida-hook-build-fields.js`         | Frida: logs android.os.Build fields (read-only diagnostic)                                               |
| `frida-hook-crypto.js`               | Frida: hooks cryptographic operations for analysis                                                       |
| `frida-hook-file-exists.js`          | Frida: logs File.exists calls matching root/emulator/frida patterns                                      |
| `frida-hook-intent.js`               | Frida: logs Intent creation and dispatch                                                                 |
| `frida-hook-network.js`              | Frida: logs network traffic and socket connections                                                       |
| `frida-hook-shared-prefs.js`         | Frida: logs SharedPreferences reads/writes                                                               |
| `frida-hook-url-log.js`              | Frida: logs URL construction and OkHttp requests                                                         |
| `frida-hook-webview.js`              | Frida: hooks WebView load and JavaScript interface calls                                                 |
| `frida-hooks-test.sh`                | Unit tests verifying hook files exist and use `Java.perform`                                             |

---

## Conventions

- `_` prefix for sourced libraries (`_helpers.sh`, `_spoof-table.sh`, `_emulator.sh`, `_frida.sh`, `_mitm.sh`, `_spoof.sh`, `_status.sh`, `_tmux.sh`) — no `set -euo pipefail`.
- Frida hooks follow: `Java.perform(function() { ... })` with tagged console output (`[cert-bypass]`, `[url-log]`, etc.).
- Spoof table is the single source of truth for device identity.
- Environment-variable-driven: ~30 env vars (`AVD_NAME`, `FRIDA_VERSION`, `MITM_PORT`, etc.) with sensible defaults.
- 10-phase start sequence in `re-avd.sh start` is strictly ordered.

---

## Gotchas

- `_spoof-table.sh` and `frida-spoof-build.js` must be kept in sync — both define the Pixel 7 spoof profile independently.
- `frida-spoof-build.js` patches Build fields AND hides emulator files. `frida-hook-build-fields.js` is read-only/diagnostic only.
- `re-avd.sh start` kills ALL running emulators on start — be careful if other AVDs are running.
- Frida server deployed to `/data/local/tmp/` on the emulator (configurable via `FRIDA_BIN`).
- `opencode-android-re.sh` reads `ANDROID_RE_OPENCODE_PROFILE` env var (set by Nix wrapper).
- `findings.sh` defines the Android schema/projection; shared command behavior lives in `../_findings-common.sh`.
- Niri window rule matches title `^android-re` — do not change the Ghostty title without updating niri config.
- Runtime tools required: `adb`, `emulator`, `frida`/`frida-ps`, `mitmdump`, `apktool`, `jadx`.

---

## Dependencies

- `../../lib/logging.sh`, `../../lib/require.sh` (via `_helpers.sh`), `../../lib/test-helpers.sh`
- Nix modules: `ai-agents/android-re/` (wrapper binaries, prompt injection)
- Nix helpers: `ai-agents/android-re/_launchers.nix` wraps `opencode-android-re.sh`
