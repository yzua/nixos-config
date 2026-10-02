# Selected rooted Android lab

## Implemented owned-emulator lifecycle

`pi-re doctor [--json]` reports capabilities read-only without live probes.
`pi-re android create|start|status|root|stop|reset [--json]` owns one configured
emulator. Selection comes from setup configuration (AVD/image/API/ABI/port),
**not a caller serial flag**. Read installed help for supported options; only
`start` supports `--visible` intent. Defaults and resource limits come from setup;
do not substitute another device/image/port by guessing flags.
`pi-re init` initializes the writable profile, not an Android device. There is no
assumed Android `setup/init` command or automatic create/start/root at profile init.

- `create`: creates approved owned emulator state from the provisioned SDK image;
  missing pinned image blocks rather than downloading an SDK package.
- `start`: starts the owned emulator with a finite configured readiness budget,
  then roots and verifies same-serial UID0. `--visible` requests a visible window;
  default launch is headless. Retrying an already running owned lab rechecks root.
- `status`: process-only/read-only. Reports selected serial, owned process state,
  stale lease and `rooted: "uninspected"`; never invokes ADB, boots, roots or
  installs. It is not fresh API/ABI/app/root readiness evidence.
- `root`: verifies owned selected identity, runs `adb root`, waits boundedly for
  reconnection and verifies shell UID **0** on that same serial.
- `stop`: only the owned selected emulator/run; retain evidence first.
- `reset`: destructive owned-lab mutation; approve it explicitly and stop first.

Initial supported lab is rooted API35 `google_apis` **x86_64**, emulator first.
Apply the [contract](../../../contract.md#interfaces) to capability coverage.
Record AVD/image revision, reported serial, API/build/ABI, package/version/signature
and owner. Other Android builds/physical devices are outside the supported owned
wrapper path: production/
Play Store images can reject adb root. No device/root means runtime blocked;
static work can continue independently.

## Small wrapper baseline

For owned-lab lifecycle work covered by the request:

```bash
pi-re android status --json
# Process-only state; root is uninspected. Approved provisioning is separate:
pi-re android create --json
pi-re android start --json
pi-re android root --json
```

Expected: configured owned serial and state; successful start/root includes UID0
verification. Do not reinterpret status as an ADB probe or run mutations just to
answer intake. No per-command approval is needed for routine work already covered
by the owned-lab provisioning authorization. Preserve actual blocked/timeout/error
outputs; a root request or earlier passing check is not current root proof.

## Direct ADB for in-scope diagnostics

Use provisioned platform-tools revision, `adb version`, `adb help` and primary
[ADB documentation](https://developer.android.com/tools/adb). Device shell commands
vary with API/build; matching installed help is authority. Bind `SERIAL` to the
explicit approved identity; every direct call uses `-s`, never ambient selection.

```bash
adb -s "$SERIAL" get-state
adb -s "$SERIAL" shell getprop ro.build.version.sdk
adb -s "$SERIAL" shell getprop ro.product.cpu.abi
adb -s "$SERIAL" shell id -u
```

These are live guest diagnostics, unlike Android status. Expected: `device`, API,
ABI and UID, with errors separate. For an approved direct root operation:

```bash
adb -s "$SERIAL" root
# Wait boundedly for the same verified serial to reconnect.
adb -s "$SERIAL" shell id -u
```

Require checked root success, same-serial identity/reconnection and UID0.
Refusal/nonzero UID blocks; `su` is not an unreviewed fallback. Prefer the bundled
owned-lab wrappers, which control selection/ownership/root revalidation.

## Runtime channels, traffic and recovery

`pi-re device` controls Android serial/session/state and verifies owned root;
read the UI guide before first snapshot/helper deployment. `pi-re frida` manages
matched pinned server/attach work; read its guide first. Both can contact/root
the guest; Frida status is not a no-probe read-only report. Device help/version
are offline. Verify current ownership/root and compatibility rather than treating
an earlier successful check as current readiness.

For bounded direct logs read device `logcat --help` to select PID/tags/window/
record limits. Save privately, record truncation/PID restarts. Screenshots/files
need release approval. ADB coordinates/keycodes are not semantic UI proof;
scrcpy remains a human companion.

Use the contract's scope for owned-lab routing/trust/capture; record owned
forwards/reverses, proxy, CA, permissions and original values. Load
`web-protocol` before capture/replay;
no custom flow harness is assumed. User/system/debug CAs and pinning differ;
root does not establish complete TLS visibility.

Serialize selected-device mutations. Reconcile uncertain outcomes before retry.
Stop only owned runtime/server/UI/capture work, restore approved mappings/trust/
settings and record remaining helper/IME/root state. No global ADB restart,
foreign-claim release or unrelated emulator cleanup. Frida stop stops its server;
it does not promise removal of guest server/log files. Preserve private evidence.
