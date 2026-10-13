# Separate Pi RE foundation

`pi-re` is an autonomous **host-mode** profile, not a sandbox. Normal coding Pi,
its extensions, skills and ordinary launch behavior are unchanged. Read the authoritative
[open-box autonomy rule](contract.md#open-box-autonomy) for task scope and capture
semantics. This rooted Android foundation does not certify every RE workflow.

## Profile and launch

Home Manager installs `pi-re` on the user's `PATH`. Run it from any investigation
folder; neither the configuration checkout nor `nix develop` is needed at runtime.
The launcher uses absolute Nix-store paths for its bundled skills, prompts and
pinned tools. The current folder is the work area, not a source of agent resources.

```bash
pi-re                              # interactive RE chat from any directory
pi-re doctor --json                # read-only tool availability
pi-re lab start --visible --json    # or ask the AI to prepare the owned lab
pi-re --continue                   # latest conversation for the current folder
pi-re --resume                     # choose a saved RE conversation
```

Opening the chat does not automatically start the emulator; give the AI a scoped
investigation goal and it can prepare and operate the lab itself. Sessions and lab
state remain in the independent RE profile when you change working folders.

For development or use before Home Manager activation, `nix run .#pi-re -- ...`
is an optional alternative **from the configuration checkout**. From elsewhere,
use `nix run /path/to/config-checkout#pi-re -- ...`. These alternatives are not
needed for the installed global command.

Initialization copies selected provider/model
settings, `models.json` and `auth.json` once into independent writable files under
`${XDG_DATA_HOME:-$HOME/.local/share}/pi-re/agent`. Sessions and lab state live under
`${XDG_STATE_HOME:-$HOME/.local/state}/pi-re`. No secrets enter the Nix store; copied
OAuth refresh tokens can require a separate login after token rotation. Subsequent
initialization preserves the RE copy rather than synchronizing it.

The launcher retains Pi's default system prompt and explicitly loads the compact
contract, ten reviewed adapter/domain skills and seven prompts. Roots additionally
load the matching official REA skill (version 37) and all six upstream references. Ambient context, project trust,
skills, extensions, themes and prompts are suppressed. Foreign session files and
resource-control flags are rejected. The root profile explicitly loads only its
reviewed RE and named research-worker extensions plus shared user-question,
web-search and page/PDF-fetch extensions, the pinned official Herdr reporter and
native MCP/codemode built-ins. Runtime Flash children load no extensions;
research workers load only their read-only source tools and web extensions.
A reviewed extension registers only the pinned `rea` server for the current
root session; no `mcp.json` is written. Startup rejects existing RE-profile MCP
server registrations (including a custom server named `rea`) intact rather than
connecting/overwriting them. Coding/project MCP configuration is never imported. These root integrations are explicit immutable
resources, not discovery of the coding profile's mutable extension directory.
Questions report blocked/working/idle to Herdr and use its existing notification
transport (including tmux focus forwarding). Headless Flash helpers/children strip
inherited Herdr, tmux and outer-subagent identity.

Herdr's cold restore reconstructs `pi --session PATH`. The managed `pi` dispatcher
routes paths in the caller's `${XDG_STATE_HOME:-$HOME/.local/state}/pi-re/sessions`
through `pi-re`, preserving the RE contract, resource whitelist and independent
profile. Normal coding invocations pass unchanged to the same pinned Pi binary.
For manual resume in either terminal, use `pi-re --continue`, `pi-re --resume`, or
`pi-re --session PATH`. Flash job artifacts are not interactive root sessions and
cannot be promoted through this dispatcher. Runtime RE delegation remains bounded and non-resumable. Named read-only
research workers now support completed-turn follow-ups in their private native
sessions; regular Pi's interactive live subagents remain a separate feature.

 Main sessions are configured
privately for Z.ai Coding Plan GLM-5.3/high, with GLM-5.3-Flash/high for fresh
180-second runtime child jobs (maximum two, 16 KiB summaries). The same Flash
model powers the separate four-slot named research pool. GPT/copied providers remain
available. Credentials and model defaults remain independent writable state,
never Nix secrets. The Coding Plan endpoint is `https://api.z.ai/api/coding/paas/v4`.
REA 6.4.0 provides native, Android, JavaScript/Electron, portable managed/package,
network and runtime Evidence workflows through CLI and root-only native MCP.
Optional engines and broader scanner/gateway packs remain unfinished.

`python3 tests/pi-herdr-reporting.py` checks the pinned reporter with a fake socket.
`python3 tests/pi-resume-dispatch.py` checks profile-safe restore routing, and
`python3 tests/pi-re-loader.py --pi /path/to/pinned/pi` checks the real loader.
`python3 tests/pi-herdr-re.py --pi /path/to/pinned/pi` uses only a private temporary
profile and named Herdr/tmux session to verify actual questions and cold restoration
without credentials or model calls. It seeds a native fixture conversation because
Pi does not persist an empty chat until its first assistant turn.

## Public web research

Root sessions expose `web_search` and `web_fetch` using the same immutable
extension bundle as coding Pi, but never discover the coding extension directory.
Search routing comes from `setup.pi.webSearch`, independently of the chat model;
credentials resolve from the independent RE profile. A missing search model,
credential or compatible backend fails explicitly, without a coding-login fallback.
Existing RE credentials/models are not refreshed by activation; configure or log
in to the search provider in that profile when needed.

Search sends only the query, not conversation history. Keep private target data
out of queries and URLs. Page/PDF/plain-text extraction runs locally and sends
neither browser cookies nor provider authentication to source pages. External
content is untrusted evidence. JavaScript-rendered pages may need the existing
`re-browser` skill, whose dedicated daemon/browser ownership prerequisites still
apply for interactive work. `pi-re browser read URL` now supplies a one-page
owned documentation fallback; runtime Flash children remain unchanged. Named
research workers use the web tools through their explicit read-only allowlist.

The loader fixture exercises HTML/PDF/text extraction and separate-provider search
against loopback sources with synthetic RE credentials, including query privacy
and source-request authentication isolation. The shared extensions retain their
existing response limits and regressions in `tests/pi-extensions.py` and
`tests/pi-web-search.py`.

## Named research workers and documentation browser

Root sessions expose `research_subagent` and `research_subagent_message` for
public-documentation and source review. Give each worker a lowercase name and
specific approved source directory. There are **four concurrent research slots**
across the caller's RE profile, separate from the two existing runtime RE slots.
`setup.pi.research` sets concurrency (1–4), default turn duration (600 seconds)
and maximum duration (1800 seconds). The per-call `timeout_seconds` can choose
another finite duration within that ceiling. Nesting stays disabled.

A call runs until its turn completes, then returns a bounded summary. Follow-ups
resume that worker's native conversation with its original source root and tools;
only new-turn output is returned. This is not a background acknowledgement/live
steering interface. Names are parent-session-scoped: resume the root session to
reuse its names. Workers have bounded source-reading/listing and web tools only,
not shell, file edits, REA/MCP, device controls or browser lifecycle. Known private
configuration/key filenames, outside paths, symlinks and binary reads are excluded;
that is not a complete secret detector or an OS sandbox.

Kernel-held capacity/writer leases and PID/start/boot evidence prevent concurrent
writers. A crashed known writer can resume one private native file matching its
allocated UUID after the writer is dead. Unknown startup/writer ownership blocks
resume. An immutable runtime/loadout change also blocks resume; create a new name
rather than silently replaying a different policy. Native transcripts are capped
at 16 MiB. Cancellation stops only the invocation's owned process group.

The reviewed `/plan`, `/review` and `/handoff` prompts add research planning,
independent source review and continuation notes without importing ambient coding
skills/extensions. Existing RE prompts remain available.

For a JavaScript-rendered documentation page, load `re-browser` and use:

```bash
pi-re browser read "$DOC_URL" --json
```

This root-only route pins the existing Chrome DevTools CLI/browser, creates a
fresh scoped daemon and private browser profile, opens one approved page, saves
and returns a snapshot capped at 64 KiB, then closes its page and owned daemon.
It excludes personal cookies/provider environment secrets, disables CLI input,
network inspection and arbitrary evaluation, and disables telemetry/update checks.
Page JavaScript and network requests still run; no host containment is claimed.
Unknown ownership/partial cleanup retains a private recovery record rather than
signaling unrelated processes. It is not a general interactive RE browser launcher.

`tests/pi-re-research.py` verifies four-slot admission, exclusive/native resume,
finite deadlines and real-Pi read-only tool behavior using mock providers.
`tests/pi-re-browser.py` checks owned lifecycle with synthetic daemons;
`PI_RE_BROWSER_LIVE=1 python3 -B tests/pi-re-browser.py` additionally reads a harmless
JavaScript-rendered loopback page in real Chrome. No external target/account/model
is used. The root loader also executes actual named-worker creation and follow-up.

## Pinned REA CLI and native MCP

Use the globally installed launcher from any investigation folder:

```bash
pi-re rea --version
pi-re rea doctor --provider ghidra --json
pi-re rea function "$BINARY" "$FUNCTION" --provider ghidra --json
pi-re rea inspect-android-method "$APK" "$CLASS" "$METHOD" --json
pi-re rea analyze-javascript-application "$APP_TREE_OR_ASAR" --json
```

REA 6.4.0, official Ghidra 12.1.4, full JDK21 and the headless Android engine
0.7.1 are pinned/hash-verified through `packages/rea/`; no upstream setup,
Hopper installation, npm bootstrap or coding-profile changes are needed.
`pi-re doctor` reports installed static facts without starting Java;
`pi-re rea doctor --provider ghidra` additionally probes Java/engine readiness.

The root connects its own REA stdio MCP server using Pi's native support and
codemode exposure. This exposes all 170 advertised tools, including persistent
native sessions, call graphs/batch queries, naming and retained Evidence/unknown
ledgers. Search/describe tools on demand instead of putting every schema into each
model request. The matching `reverse-engineer-anything` upstream skill is loaded
unchanged, including references and MIT attribution; our adapter/contract replaces
its npx/setup repair recipes with managed Nix maintenance. Open/close only owned
native sessions and export private Evidence before shutdown. Another root/child
must not write the same Ghidra project.

The root and children discover the reviewed `rea-analysis` adapter skill. Native and
Android skills and all four prompts route to it; the agent calls the CLI through
Bash. Native queries explicitly select Ghidra. REA runs with isolated private
HOME/XDG directories under the RE state, pinned engine paths and a short temporary
parent. Each native CLI call imports into a disposable Ghidra project and closes
it; repeated calls can reimport. Evidence JSON/snapshots are saved only at
caller-selected paths, not automatically released to the model.

All 125 non-installer primary/alias CLI routes are enabled, including saved
HAR/native mitmproxy inspection, browser/Electron/process scenarios, Android
resource decoding, artifact extraction and reconstruction comparisons. Existing
pinned mitmdump 12.2.3, Apktool, Chrome and NixOS resource-limit paths are supplied
explicitly. The ADB transport filters enumeration and binds every operation to
the setup-selected running owned/rooted emulator while holding its lifecycle lock;
it does not implicitly boot/root or change trust/proxy state. Prepare the owned
lab first. Our coordinated lab/Frida/device tools remain available.

Upstream setup/update/uninstall and caller-selected transport/update flags remain
excluded; Nix owns maintenance. Roots use managed MCP; children remain CLI-only.
Runtime scenarios can execute code/send requests and are not sandboxes. Passive
browser CDP observation requires an explicit dedicated debugging endpoint; a
Chrome executable alone does not imply an already-running approved browser.

Some command routes remain capability-dependent: IDA/Hopper/JEB need licensed
installations, firmware needs Binwalk/Unblob plus extractors, ELF layout/core
needs the exact pwntools/pyelftools/Unicorn combination, JS source recovery needs
Wakaru, and Apple/Windows runtime branches need their matching host. None is
silently installed. The [command guide](skills/rea-analysis/references/commands.md)
records these boundaries; exposed is not the same as qualified.

Read [REA commands/limits](skills/rea-analysis/references/commands.md) before
queries. Pseudocode is reconstructed, static references are not runtime calls,
and REA Android does not replace split/resource/signature/smali tooling.
Upstream's whole-host audit currently flags NixOS as unsupported; that
informational distribution check can make `environment_healthy` false while the
scoped Ghidra checks and actual analysis succeed. Evaluate the explicit scope,
not unrelated optional-engine/agent-registration checks.

For a backend smoke check, build the owned native fixture and run the explicit
integration suite (no target execution or real model calls):

```bash
nix build --no-link --print-out-paths .#pi-re .#rea-fixture
python3 -B tests/pi-re-rea-integration.py --pi-re "$PI_RE_BIN" --native "$FIXTURE_ELF"
```

Set those variables from the printed store paths (`bin/pi-re` and
`bin/rea-fixture`). This integration test is opt-in because it starts Java/Ghidra,
may take several minutes and writes private scratch evidence; it is not part of
`just test`. The offline route regression is `tests/pi-re-rea.py`.

Additional opt-in network/runtime/MCP qualification uses only synthetic saved
captures, a harmless PTY process and an owned loopback web page:

```bash
python3 -B tests/pi-re-rea-workflows.py --pi-re "$PI_RE_BIN" \
  --native "$FIXTURE_ELF" --browser "$CHROME_BIN" --python "$RE_TOOLCHAIN_PYTHON"
```

Supply those absolute executable paths from the configured runtime. Omitting
optional arguments skips their fixture branches. This checks all 170 advertised
tools, CLI/MCP HAR inspection, native mitmproxy decoding, PTY capture, persistent
Ghidra open/query/close and a fresh owned Chrome click/network scenario. It never
attaches to a personal browser, calls an external site, boots a device or uses a
real model. A passing fixture does not qualify arbitrary targets or optional
engines; real-device REA acquisition remains untested.

Owned-fixture backend coverage includes native function/string/xref/instruction/
decompilation, missing-symbol/malformed-input failures, Android package/class/
method/reference queries and a JavaScript/Electron IPC/import graph. Checks
preserve original hashes and verify no new Ghidra runtime directories remain.
This establishes these fixture paths, not blanket support for arbitrary apps.
The installed loader additionally executes the Pi Bash tool and pinned REA
version check with an empty ambient tool PATH.

A live agent trial naturally loaded the reviewed skills, recovered both native
functions and their caller relationship, and correctly qualified the global's
initial value rather than claiming an invariant. It also made/corrected shell
and JSON-shape mistakes and used three native invocations against a requested
two-query budget. This is successful discovery/analysis evidence, not strict
budget-accounting qualification; host-mode safeguards remain behavioral.

## Owned rooted emulator

The copy-sensitive `setup.androidLab` selects the only supported initial image:
API 35, Google APIs, x86_64, **non-Play**. The SDK is composed by Nix, not modified
with `sdkmanager`. Host KVM access is required. Setup selects SwANGLE software
rendering with host hardware-video decoding disabled; a real ARM64 app exposed a
host crash with direct SwiftShader. This is a tested compatibility workaround,
not a guarantee for every app/GPU path.

Setup also selects a 720×1600 framebuffer at 320 DPI through optional
`setup.androidLab.display = { width = 720; height = 1600; density = 320; };`.
Width/height accept integers from 240–4096 pixels; density accepts 72–640 DPI.
Before a new launch, the lifecycle wrapper atomically updates only `hw.lcd.*`
display keys in the owned private AVD's `config.ini` and passes `-skin WIDTHxHEIGHT`.
It never uses the obsolete, ignored `-dpi-device` flag. Existing running emulators
are reused without config writes or implicit live resizing; stop/start applies a
changed selection without resetting user data. Omitting `display` retains the
existing AVD settings and launch behavior.

```bash
pi-re android create --json
pi-re android start --json          # boot deadline, then adb root and UID 0
                                     # plain boot: NO proxy/CA/capture/Frida —
                                     # check lab leftovers first (lab.md Lifecycle)
pi-re android status --json         # process-only; no ADB probe or root claim
pi-re android root --json           # explicitly reverify root
pi-re android stop --json
pi-re android reset --json          # only after stop; destroys this owned AVD
```

`start --visible` requests a window. Every operation uses the setup-selected serial,
private AVD paths, a nonblocking lifecycle lock and a host PID/start/session lease.
No `sudo`, global emulator kill, SDK download or ADB-server shutdown is performed.
ADB is the shared local transport daemon; the wrapper never claims ownership of it.

## Device and Frida interfaces

```bash
pi-re device help snapshot
pi-re device open '<authorized.package>' --json --no-test-ime
pi-re device snapshot --json
pi-re device click '@e1' --json       # only a ref from the latest snapshot
pi-re frida setup
pi-re frida run --package '<running.package>'
pi-re frida stop
pi-re device close --json
```

The device wrapper controls configuration, local socket transport, selected serial,
private state and session. It allows initial UI commands, not cloud/infrastructure,
batch/replay, emulator shutdown or caller transport overrides. First snapshot may
install the pinned bundled helper on this approved lab; record its changes. IME
activation is separate; `--no-test-ime` avoids it during basic qualification.

Frida core/server are matched at 17.5.1. `run` is attach-only, has a 30-second parent
deadline, and demonstrates native messages/RPC by default. `--script` accepts task
JavaScript; it does not implicitly provide Java or retain later-action hooks.
The official pinned frida-tools package contains its Java bridge; the supported
CLI and owned-fixture check explicitly use it without npm/pip downloads. Frida
status contacts the selected rooted guest. Shutdown verifies boot/PID/start/exe
through a guest pidfd helper, never a bare PID signal. Reboot-stale records are
archived without signaling old PIDs. Private command artifacts are not sanitized
release evidence. A daemon request may need explicit recovery after a timeout.

## One-command lab and end-to-end check

```bash
pi-re lab start --visible --json     # default all-hostname forward capture
# Optional narrow capture instead (stop an active lab before changing mode):
# pi-re lab start --allow-host api.example.test --json
pi-re lab status --json
pi-re lab stop --json
pi-re lab check --json
```

Read [coordinated lab guide](skills/android-runtime/references/lab.md) first.
Start automates boot/root, dedicated forward capture, **guest system CA** trust,
lab-only proxy and Frida. Default and optional exact-host modes follow the
[contract](contract.md#open-box-autonomy); different active capture configuration
is refused until stopped. Host/browser trust and unrelated devices are untouched.
SELinux stays Enforcing; API35 Conscrypt/zygote overlays are boot-scoped. Restart
existing target apps after trust changes. System trust does not bypass TLS pinning,
root detection or Play Integrity. Stop restores only owned proxy settings and
independently attempts all owned cleanup, including private device-session/daemon
retirement and guest filesystem sync; report and recover partial failures. The
pinned device package uses Nix procps for safe recorded process identity. Without
`--visible` the emulator runs headless.

`lab check` has a separate 600-second aggregate budget. It verifies an actual UI
click → Java hook → Counter change, default Android HTTPS system trust → verified
upstream TLS → nonce-correlated decrypted capture, denied unapproved CONNECT and
proxy restoration. It only replaces a signer-verified owned fixture, leaves a
usable default all-host forward-capture lab on success, without the temporary
fixture-origin mapping, and attempts whole-lab cleanup on failure.
Reports and raw flows are private under the caller's RE state.

## Verification and readiness

```bash
python3 -B tests/pi-re-config.py
python3 -B tests/pi-re-rea.py
python3 -B tests/pi-re-android.py
python3 -B tests/pi-re-runtime.py
python3 -B tests/pi-re-traffic.py
python3 -B tests/pi-re-subagent.py
python3 -B tests/pi-re-lab.py
python3 -B tests/pi-re-loader.py --pi-re "$(command -v pi-re)"
just check
just home-preview
```

The loader check runs the installed global wrapper from an unrelated hostile
working folder, using isolated HOME/XDG paths, synthetic preinitialized credentials
and a loopback mock provider. It verifies all ten skills, the contract, model-visible
tools, packaged capability availability and private sessions without reading the
coding login, starting a device or calling a paid model. For the built profile it
also checks the upstream skill and native MCP/codemode namespace. The `--pi` alternative
checks checkout resources with an explicitly supplied Pi executable.

`tests/fixtures/pi-re-android/` supplies a locally built counter/HTTPS APK for
UI/static/native/Java/traffic qualification. It has INTERNET permission, a narrowly
selected owned HTTPS fixture URL, and no custom TLS trust manager or accounts. Its
short-lived signing key stays in a temporary directory, never Git/store outputs.
Recorded live coverage includes **two cold owned-fixture checks** and **two fresh
agent trials covering natural-language and explicit UI workflows**, all passing.
These results cover the owned UI → Java hook → HTTPS capture path, not arbitrary
apps or completed negative/adversarial and broader capability packs. Doctor's
qualification labels are coverage notes under the [contract](contract.md#interfaces),
not a blanket block on in-scope analysis. Activation does not create, boot, root,
instrument or reset a device.
