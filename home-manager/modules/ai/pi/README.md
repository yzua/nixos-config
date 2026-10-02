# Pi configuration

Home Manager links the global instructions, prompts, agent profiles, and four
locally owned Amos extensions. Settings, custom models, credentials, sessions, and
Herdr's extension remain writable and separately owned.

The first activation backs up existing settings/models beneath
`${XDG_STATE_HOME:-$HOME/.local/state}/pi-config/backups/`, selects GPT-6.1 Sol
at high, disables native MCP, and adds the model to the existing custom
Responses provider if needed. Its existing endpoint limits and credentials
are preserved. Later activations preserve settings saved in Pi.

Run `p` inside Herdr or tmux. Inside Herdr, each subagent gets a separate named
background tab in the caller's live workspace. The parent keeps its full size and
focus; completed runs close only their owned pane (and its now-empty tab).
Inherited outer tmux variables are ignored; direct tmux sessions keep their existing
layout and behavior. Nix's Herdr package embeds its desktop notification helper.
Tmux focus events must stay enabled: Herdr suppresses alerts for its focused tab
unless it receives outer-terminal focus loss. Other Herdr tabs still alert.
After switching Home Manager, reload existing Pi sessions to load changed extensions.
Detach and reattach existing tmux clients once so outer desktop focus reports are
requested; new clients use the configured focus forwarding automatically.

`/thinking` changes the main level; Ctrl+S saves a new
default. Scout starts at medium; researcher, worker, and reviewer at high.
Profiles use the configured default model and resolve the provider from the
caller's settings. `/plan`, `/review`, and `/handoff` are reusable prompts.
Alt+S or `/snippets` toggles Verify and Delegate exploration for one message.

Select `system` under Theme in `/settings` to inherit the terminal palette,
including this workstation's Gruvbox Dark Soft colors. A saved `dark` selection
uses Pi's own palette. Theme choices stay in writable `~/.pi/agent/settings.json`;
`/reload` applies settings changes to a running Pi session.

Web fetch extracts pages/PDFs locally. Failed extraction directs the agent to the existing
Chrome DevTools CLI skill rather than automatically sending URLs to Jina.
Pi has no MCP tools configured; the Chrome CLI retains its own daemon.

Edit TypeScript directly in `extensions/`: `ask-user-question.ts`,
`prompt-snippets/index.ts`, `web-fetch/index.ts`, and
`interactive-subagents/pi-extension/subagents/`. Agent profiles and prompts
are alongside this README. Stage new files, run the checks and Home Manager
preview, then `just home-switch` and `/reload` in Pi to load edits.

The initial sources were copied from `amosblomqvist/pi-config` commit
`f82da563ab05d66729492d64c7ed4e96db3663f3` and
`amosblomqvist/pi-interactive-subagents` commit
`c3e8b53c0754ae5ccc19fdab5a7481ec039bc2f7`. Source files, lockfiles, and the
subagent license/tests are in this repository; builds use those local files.
The extension's bundled `agents/` retains upstream fallback examples. This
workstation's configured profiles in the adjacent `agents/` directory override
those examples; edit the configured profiles for local model/tool policy. An
alternate Pi profile without those overrides can select the upstream fallbacks,
whose model and tool requirements differ and must be reviewed before use.
Web-fetch dependencies use the
upstream npm lockfile with lifecycle scripts disabled. Pi provides extension
API and TypeBox imports, including legacy aliases.

The subagent source passes `--thinking` independently of `--model`, so a
profile can inherit the configured model while selecting its own reasoning
level. This applies to both initial launches and resumed follow-ups.

`managed-run.ts` owns process setup, supervision, cleanup, and result delivery
for both initial and resumed runs. Resumes replay saved restrictions and report
only new output. Disposed runtimes stop delivering results without terminating
children solely because of a reload or session replacement. Durable ownership
claims prevent a second writer after reload or parent restart; surviving or
uncertain ownership refuses resume until exit is established. Corrupt metadata,
an abandoned launch lock, or a different multiplexer server also refuses resume rather
than guessing that it is safe.

Children publish terminal errors and shut down at `agent_settled`, after Pi's
retries and queued continuations finish. Pending questions and nested children
keep the session open. A missing pane gets a two-second grace period for its
final sidecar, then reports failure; healthy panes have no job timeout.
Spawns and resumed follow-ups use `--approve`, matching `p`'s automatic project
trust. Explicit and default names get suffixes when needed, preserving finished
children's handles for later follow-ups.

Use `nix develop`, then `just fmt-check` and `just lint-ts` when editing the
extensions. `python3 tests/pi-config.py` and `python3 tests/pi-subagents.py`
check writable-config migration and child reliability through the installed Pi
loader, with isolated settings, a mock provider, and
fake tmux. `python3 tests/pi-herdr.py` checks native Herdr selection even with
outer tmux variables, atomic input, separate named tabs, ownership across server
replacement, and pane-loss reporting. `python3 tests/pi-herdr-live.py` checks real
tab naming, focus/geometry preservation and cleanup in its own temporary session.
`python3 tests/pi-resume-dispatch.py` checks that Herdr's `pi --session` restore
command routes RE root sessions through `pi-re`; ordinary coding Pi is unchanged.
After activation, `python3 tests/pi-herdr-focus.py`
uses a separate tmux server and named Herdr session to check real desktop attention
alerts with focus forwarding disabled/enabled (requires a graphical session and strace).
`python3 tests/pi-extensions.py` exercises web/PDF extraction,
question answers/cancellation and Herdr waiting events, and the optional
`safe_bash` tool through Pi's loader. It uses local HTTP fixtures and the
installed web-fetch dependencies; set `PI_WEB_FETCH_DIR` to use another dependency
directory. These tests make no paid model calls. Set `PI_BIN` to test another Pi binary.
Run `just check` and `just home-preview` before activation. Smoke-test browser
use and real tmux subagent completion/follow-up with the installed Pi.
