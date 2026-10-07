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
contract, ten reviewed skills and four prompts. Ambient context, project trust,
skills, extensions, themes and prompts are suppressed. Foreign session files and
resource-control flags are rejected. The root profile explicitly loads only its
reviewed `re_subagent` extension plus the shared user-question UI and pinned official
Herdr reporter; children load none. These root integrations are explicit immutable
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
cannot be promoted through this dispatcher. RE delegation remains bounded and
non-resumable; regular Pi's interactive subagents are a separate feature.

 Main sessions are configured
privately for Z.ai Coding Plan GLM-5.3/high, with GLM-5.3-Flash/high for fresh
180-second child jobs (maximum two, 16 KiB summaries). GPT/copied providers remain
available. Credentials and model defaults remain independent writable state,
never Nix secrets. The Coding Plan endpoint is `https://api.z.ai/api/coding/paas/v4`.
The REA static pack is provisioned for native, Android and JavaScript/Electron
queries. MCP, broader browser/scanner/gateway packs remain unfinished.

`python3 tests/pi-herdr-reporting.py` checks the pinned reporter with a fake socket.
`python3 tests/pi-resume-dispatch.py` checks profile-safe restore routing, and
`python3 tests/pi-re-loader.py --pi /path/to/pinned/pi` checks the real loader.
`python3 tests/pi-herdr-re.py --pi /path/to/pinned/pi` uses only a private temporary
profile and named Herdr/tmux session to verify actual questions and cold restoration
without credentials or model calls. It seeds a native fixture conversation because
Pi does not persist an empty chat until its first assistant turn.

## Pinned REA static backend

Use the globally installed launcher from any investigation folder:

```bash
pi-re rea --version
pi-re rea doctor --provider ghidra --json
pi-re rea function "$BINARY" "$FUNCTION" --provider ghidra --json
pi-re rea inspect-android-method "$APK" "$CLASS" "$METHOD" --json
pi-re rea analyze-javascript-application "$APP_TREE_OR_ASAR" --json
```

REA 4.1.0, official Ghidra 12.1.4, full JDK21 and the headless Android engine
0.7.1 are pinned/hash-verified through `packages/rea/`; no upstream setup,
Hopper installation, npm bootstrap or coding-profile changes are needed.
`pi-re doctor` reports installed static facts without starting Java;
`pi-re rea doctor --provider ghidra` additionally probes Java/engine readiness.

The root and children discover the reviewed `rea-analysis` skill. Native and
Android skills and all four prompts route to it; the agent calls the CLI through
Bash. Native queries explicitly select Ghidra. REA runs with isolated private
HOME/XDG directories under the RE state, pinned engine paths and a short temporary
parent. Each native CLI call imports into a disposable Ghidra project and closes
it; repeated calls can reimport. Evidence JSON/snapshots are saved only at
caller-selected paths, not automatically released to the model.

The enabled route covers static native/Android/JavaScript queries and evidence
operations. Upstream setup/update/uninstall, MCP and REA runtime capture are
excluded from this wrapper. Nix owns dependency maintenance; our rooted lab,
Frida, device and traffic tools remain the runtime workflow. This routing is not
a host sandbox or a restriction on ordinary in-scope Bash.

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
coding login, starting a device or calling a paid model. The `--pi` alternative
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
