# Separate Pi RE foundation

`pi-re` is an autonomous **host-mode** profile, not a sandbox. Normal coding Pi,
its extensions, skills and launcher are unchanged. Read the authoritative
[open-box autonomy rule](contract.md#open-box-autonomy) for task scope and capture
semantics. This rooted Android foundation does not certify every RE workflow.

## Profile and launch

```bash
nix run .#pi-re -- doctor --json
nix run .#pi-re -- init
nix run .#pi-re -- --print 'Plan an authorized Android investigation; do not mutate targets.'
```

Home Manager also installs `pi-re`. Initialization copies selected provider/model
settings, `models.json` and `auth.json` once into independent writable files under
`${XDG_DATA_HOME:-$HOME/.local/share}/pi-re/agent`. Sessions and lab state live under
`${XDG_STATE_HOME:-$HOME/.local/state}/pi-re`. No secrets enter the Nix store; copied
OAuth refresh tokens can require a separate login after token rotation. Subsequent
initialization preserves the RE copy rather than synchronizing it.

The launcher retains Pi's default system prompt and explicitly loads the compact
contract, nine reviewed skills and four prompts. Ambient context, project trust,
skills, extensions, themes and prompts are suppressed. Foreign session files and
resource-control flags are rejected. The root profile explicitly loads only its
reviewed `re_subagent` extension; children load none. Main sessions are configured
privately for Z.ai Coding Plan GLM-5.3/high, with GLM-5.3-Flash/high for fresh
180-second child jobs (maximum two, 16 KiB summaries). GPT/copied providers remain
available. Credentials and model defaults remain independent writable state,
never Nix secrets. The Coding Plan endpoint is `https://api.z.ai/api/coding/paas/v4`.
MCP, broader browser/native/scanner/gateway packs remain unfinished.

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
python3 -B tests/pi-re-android.py
python3 -B tests/pi-re-runtime.py
python3 -B tests/pi-re-traffic.py
python3 -B tests/pi-re-subagent.py
python3 -B tests/pi-re-lab.py
just check
just home-preview
```

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
