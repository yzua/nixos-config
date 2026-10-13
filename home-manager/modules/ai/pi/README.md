# Pi configuration

Home Manager links the global instructions, prompts, agent profiles, four
locally owned Amos-derived extensions, native web search, and opt-in network diagnostics. Settings, custom models, credentials, sessions, and
Herdr's extension remain writable and separately owned.

The first activation backs up existing settings/models beneath
`${XDG_STATE_HOME:-$HOME/.local/state}/pi-config/backups/`, selects GPT-6.1 Sol
at high, disables native MCP, and adds the model to the existing custom
Responses provider if needed. Its existing endpoint limits and credentials
are preserved. `default.nix` owns the initialization document (settings and model
metadata); `initialize.py` owns once-only application and backups. Policy edits do
not migrate initialized profiles. Later activations preserve settings saved in Pi.

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
caller's settings. Explicit models for shared-config Pi subagents must match an
exact authenticated model ID; ambiguous IDs require `provider/model`. A different
role-specific `.pi/agent` directory retains child CLI resolution (including fuzzy
matching/fallback), so prefer qualified `provider/model` values there. Claude
profiles retain their own model aliases. `/plan`, `/review`, and `/handoff` are reusable prompts.
Alt+S or `/snippets` toggles Verify and Delegate exploration for one message.

Select `system` under Theme in `/settings` to inherit the terminal palette,
including this workstation's Gruvbox Dark Soft colors. A saved `dark` selection
uses Pi's own palette. Theme choices stay in writable `~/.pi/agent/settings.json`;
`/reload` applies settings changes to a running Pi session.

For intermittent socket failures, run `/net-debug on` after `/reload`, reproduce
the failure, then `/net-debug off`. Private JSONL files under
`${XDG_STATE_HOME:-$HOME/.local/state}/pi-network/` record request sizes, response
header timing/status, allowlisted response encoding and socket codes, SHA-256
response request-ID digests, body-read counts/timing/errors, finalized assistant
errors, and compaction outcomes. They are capped at 1 MiB per activation; the
directory/file modes are 0700/0600. No URLs, raw headers, credentials, prompts,
response content, or raw error strings are logged. This observes global fetch
and the existing consumer's reader/iterator without an extra read, tee, new body
or replacement Response. It does not instrument fetch implementations that bypass
that boundary or consumption through native `response.text()`/`json()` methods.
It changes no timeout, pooling, retry or TLS behavior. Bun's native
`fetch(..., { verbose: true })` prints headers and must not be enabled unfiltered
in a credential-bearing interactive session. The ordinary Pi `--verbose` flag
only changes startup verbosity.

Web search uses the backend selected by `setup.pi.webSearch` in `flake.nix`,
independently of Pi's chat model. Home Manager writes this non-secret provider/model
choice beside the extension as `config.json`. GLM and other chat models can use
search while keeping their normal chat provider. Pi resolves the search provider's
own request-time credentials; a runtime chat API-key override on another provider
is not sent to search. The selected search model must exist in Pi's `models.json`
or provider catalog and use OpenAI Responses. A missing backend fails explicitly
rather than silently falling back to another provider. Direct source invocations
without `config.json` use the active model instead.

A `/v1` base maps to its sibling `/backend-api/codex/alpha/search`; a
`/backend-api/codex` base appends `/alpha/search`. This requires a compatible
backend such as Codex-LB; it does not make ordinary Responses endpoints support
search. Only the query is sent, not conversation history. Results are untrusted snippets with
source URLs; use web fetch to read them. Search uses live external access and
existing provider limits. The endpoint supplies no token usage, so these calls
are not added to Pi's model-token totals. Requests have a 30-second deadline,
1 MiB response cap, sanitized errors, refused redirects, and bounded output.
No new credentials, packages, or mutable profile settings are needed.

Web fetch extracts pages/PDFs locally. Failed extraction directs the agent to the existing
Chrome DevTools CLI skill rather than automatically sending URLs to Jina.
Pi has no MCP tools configured; the Chrome CLI retains its own daemon.

Edit TypeScript directly in `extensions/`: `ask-user-question.ts`,
`prompt-snippets/index.ts`, `web-fetch/index.ts`, `web-search/index.ts`, and
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

`agent-catalog.ts` owns profile parsing, package/global/project precedence, and
pinned spawn permissions. Discovery uses declared names; direct loading uses
filenames. Hidden profiles still shadow lower-precedence profiles and remain
permitted/loadable, but are omitted from the visible tool listing. Paths and files
are resolved at call time; only child permissions are pinned.

`RunStatusMonitor` in `status.ts` owns activity interpretation, timestamp/sequence
fencing, successful-send overrides, and capped stall/recovery notifications. Its
explicit-time operations leave timers, widget rendering, and Pi message delivery
in `index.ts`; supervision still observes activity when status notifications are
disabled. Interactive children update status without waking the parent.

`child-launch.ts` owns child commands, sandbox snapshot/replay, and task handoff
for both initial and resumed runs. `run-evidence.ts` interprets completion and
pane-loss evidence independently of diagnostic wording; `tmux.ts` and `herdr.ts`
own terminal operations. `managed-run.ts` retains process ownership, dispatch,
supervision, cleanup, and result delivery. Resumes replay saved restrictions and
report only new output. Disposed runtimes stop delivering results without terminating
children solely because of a reload or session replacement. Durable ownership
claims prevent a second writer after reload or parent restart. A replacement
parent recalls its own live children on the same surface and can steer them by
name; obsolete watchers cannot close them or replay their results. Token-bound
PID/start-time, boot and namespace leases let proven-dead Pi writers resume after
a mux cold restart without touching replacement-server panes. Completed runs
retain delivery tombstones; results are delivered at most once (a crash during
handoff can lose a notification). Known completed pre-v2 handles migrate only
with matching completion/launch evidence in the parent's native branch and an
old scoped launch script. Unknown ownership, active legacy runs, corrupt metadata
and abandoned launch locks remain fail-closed rather than risking two writers.
Finish active pre-v2 children before the first reload into this version.

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
loader, with isolated settings, a mock provider, and fake tmux.
`node --test tests/pi-subagents-recall.test.mjs` exercises the production catalog,
status monitor, launch, and evidence interfaces offline, plus steering,
reload/restart recall, supervisor fencing, cold recovery and legacy migration on
both backends. `python3 tests/pi-herdr.py` checks native Herdr selection even with
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
directory. `python3 -B tests/pi-web-search.py` exercises native search through Pi's loader
with local HTTP fixtures: authentication/header precedence, query privacy,
endpoint routing, separate-provider search and credential isolation, result bounds,
sanitized errors, cancellation and timeouts.
These tests make no paid model calls. Set `PI_BIN` to test another Pi binary.
Run `just check` and `just home-preview` before activation. Smoke-test browser
use and real tmux subagent completion/follow-up with the installed Pi.
