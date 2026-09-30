# Pi configuration

Home Manager links the global instructions, prompts, agent profiles, and four
locally owned Amos extensions. Settings, custom models, credentials, sessions, and
Herdr's extension remain writable and separately owned.

The first activation backs up existing settings/models beneath
`${XDG_STATE_HOME:-$HOME/.local/state}/pi-config/backups/`, selects GPT-6.1 Sol
at high, disables native MCP, and adds the model to the existing custom
Responses provider if needed. Its existing endpoint limits and credentials
are preserved. Later activations preserve settings saved in Pi.

Run `p` inside tmux. `/thinking` changes the main level; Ctrl+S saves a new
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
an abandoned launch lock, or a different tmux server also refuses resume rather
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
fake tmux. It makes no paid model calls. Set `PI_BIN` to test another Pi binary.
Run `just check` and `just home-preview` before activation. Smoke-test browser
use and real tmux subagent completion/follow-up with the installed Pi.
