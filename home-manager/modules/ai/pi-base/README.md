# Pi base and profiles

```text
pi-base                 shared executable, preferences and immutable common resources
├─ pi-coding (pi, p)     existing coding discovery and coding prompts
├─ pi-re                reviewed RE loadout, owned lab and bounded workers
└─ pi-home              personal instructions and on-demand Samsung TV controls
```

`pi-base` also opens a neutral explicit-load chat. The common extension catalog in
`resources.nix` owns questions, web search, web/PDF fetching, interactive subagents,
retry normalization, prompt snippets, network diagnostics and pinned Herdr integration.
All root profiles inherit this catalog, not duplicated implementations. Base also
provides the managed Chrome DevTools CLI and the shared `chrome-devtools-cli` skill.
Explicit-load roots select its complete pinned directory (including references);
coding keeps native discovery of the skills.sh-owned mutable copy. Loading the skill
never starts Chrome. Browser tasks must use their own page IDs and close only owned
pages; parallel general agents may share the CLI daemon. RE's additional browser
ownership/scope rules still apply. Shared agent
roles live in `agents/`; RE additionally keeps its two specialized delegation systems. Home Manager links the base extensions/instructions
into the existing coding discovery directory; Herdr retains ownership of its writable
coding reporter. Explicit-load roots use the pinned reporter directly.

For new Home/Base/RE interactive workers, a saved child policy pins the native Pi,
canonical configuration path, origin instructions/skills, explicit extension/tool
loadout and `${XDG_STATE_HOME:-$HOME/.local/state}/<profile>/interactive-subagents/sessions`.
Project agent overrides/context/extensions and cwd-local agent directories are not
automatically imported. Named resumes replay that policy; workers with delegation
grants pass it to nested workers. Historical coding loadouts keep native behavior.
Worker sessions resume through `subagent_message`, not as unrestricted root chats.
Domain policies support Pi roles; alternate Claude roles remain coding-only rather
than bypassing origin instructions and loadout restrictions.

## One live configuration, separate histories

All profiles use the **same lexical `~/.pi/agent` directory** for native auth,
models and settings, including saved model/thinking defaults and other global UI
preferences. The existing `pi-config/initialized-v1.json` policy marker is retained;
renaming the coding profile does not reapply defaults or move its sessions/sidecars.
There are no credential copies or auth/settings file symlinks: Pi 1.1.0 locks lexical
filenames, so separate aliases would not coordinate concurrent token refreshes.
Native credential refresh and settings writes remain Pi-owned. New launches observe
saved defaults; use native `/reload` or model selection for running sessions rather
than expecting instant changes in every already-running model registry.

Coding keeps native project trust/discovery and its existing session lookup.
Other root histories are under `${XDG_STATE_HOME:-$HOME/.local/state}/<profile>/sessions`.
`pi` and `pi-coding` preserve ordinary argv and dispatch explicit RE/Home/Base session
paths back through the owning launcher, including Herdr cold restore. Bare IDs stay
native coding lookups; runtime and research worker artifacts cannot become roots.
Cross-profile launches clear inherited RE helper/session overrides. A deliberately
supplied native coding `PI_CODING_AGENT_DIR` still works for custom role profiles and
isolated fixtures; it opts out of the managed shared default. RE/Home/Base ignore
that ambient override and use their canonical base path.

Close legacy RE sessions before the first activation/`pi-re init`. Migration takes
native file mutexes in both profiles and best-effort checks for old processes;
it never kills them. After an abrupt migration exit, empty caller-owned native
mutexes recover only after the native 30-second stale period and another writer
check; foreign, nonempty or changed locks stay fail-closed. This is best-effort
process detection, not guaranteed lifetime writer exclusion.

Existing RE auth/models/settings are atomically archived, without overwriting,
under `${XDG_DATA_HOME:-$HOME/.local/share}/pi-re/backups/shared-config-v1`.
A one-time, restart-safe merge adds compatible missing provider definitions, model
IDs and logins to the live base. Current Pi defaults, existing model IDs and logins
win conflicts. Missing models merge only when provider routing definitions match;
auth is not imported across conflicting endpoints. An existing login/default also
protects implicit built-in routing from legacy endpoint overrides. Unrecognized or
conflicting legacy values remain in the private archive for deliberate recovery;
no settings preferences are imported. A separate RE migration marker records the
backup path and merge policy. Reappearing legacy files block launch rather than silently selecting a stale
login. No secrets enter Nix evaluation, the store or logs.

RE and Home suppress ambient resource discovery despite sharing settings. RE's native
MCP factory has an empty file-config loader and registers only its pinned session
server; coding/project MCP files are not read or connected. Home/Base disable MCP.
Specialized RE workers retain their restricted tool/model/loadout contracts. General
interactive subagents are also available in RE and have broader role-dependent host
access; do not confuse them with the four-tool research workers. Shared configuration
is intentionally not a security boundary. See [RE](../pi-re/README.md) and
[Home/TV](../pi-home/README.md) for domain-specific behavior.

## Initial defaults and coding integrations

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

`upstream-retry.ts` normalizes only the exact assistant error
`upstream_error: native upstream response body failed` by appending `(network error)`.
This lets Pi's built-in retry policy handle it: by default, three retries after
2, 4, and 8 seconds. Existing `retry` settings, cancellation, and failed-attempt
omission remain owned by Pi; no synthetic "keep going" messages are sent.
Other errors and aborted responses are unchanged. The extension neither fixes
the upstream service nor retries indefinitely. Activate Home Manager and run
`/reload` to enable it; disable automatic retries in Pi's settings to stop retries.

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
Coding's initial settings disable native MCP; RE owns its separate session registration.
The Chrome CLI retains its own daemon.

Edit TypeScript directly in `extensions/`: `ask-user-question.ts`,
`upstream-retry.ts`, `prompt-snippets/index.ts`, `web-fetch/index.ts`, `web-search/index.ts`, and
`extensions/interactive-subagents/pi-extension/subagents/`.
Shared agent roles are in `agents/`; coding prompts remain in `../pi-coding/prompts/`. Stage new files, run the checks and Home Manager
preview, then `just home-switch` and `/reload` in Pi to load edits.

The initial sources were copied from `amosblomqvist/pi-config` commit
`f82da563ab05d66729492d64c7ed4e96db3663f3` and
`amosblomqvist/pi-interactive-subagents` commit
`c3e8b53c0754ae5ccc19fdab5a7481ec039bc2f7`. Source files, lockfiles, and the
subagent license/tests are in this repository; builds use those local files.
The extension's bundled `agents/` retains upstream fallback examples. This
caller's configured profiles in `agents/` override
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
command routes RE/Home/Base root sessions to their owning launchers and rejects
headless runtime/research artifacts; ordinary coding argv is unchanged.
`python3 -B tests/pi-profiles.py` checks base inheritance, live shared native
configuration and cross-profile environment handling. `python3 -B tests/pi-home-tv.py`
uses fake transports only; it never connects to a TV.
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
`python3 -B tests/pi-upstream-retry.py` exercises the exact upstream failure,
recovery without extra user messages, retry caps/backoff, disabled retries,
auth/quota exclusions, and cancellation through Pi's real loader with an offline
provider. These tests make no paid model calls. Set `PI_BIN` to test another Pi binary.
Run `just check` and `just home-preview` before activation. Smoke-test browser
use and real tmux subagent completion/follow-up with the installed Pi.
