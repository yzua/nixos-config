# agent-device Android wrapper and direct API

## Reviewed identity and current gates

Reviewed **v0.21.18**, source commit
`6d1314fc3024efa096eed59fdd34162467ffe5fa`, requires **Node >=22.12**.
Pin CLI/package and skill together; npm does not ship the upstream skill.
Primary tagged references:
[commands](https://github.com/callstack/agent-device/blob/v0.21.18/website/docs/docs/commands.md),
[Node client](https://github.com/callstack/agent-device/blob/v0.21.18/website/docs/docs/client-api.md),
[session example](https://github.com/callstack/agent-device/blob/v0.21.18/examples/sdk/client-session.ts),
[sessions](https://github.com/callstack/agent-device/blob/v0.21.18/website/docs/docs/sessions.md),
[security](https://github.com/callstack/agent-device/blob/v0.21.18/website/docs/docs/security-trust.md),
[package](https://github.com/callstack/agent-device/blob/v0.21.18/package.json),
[upstream skill](https://github.com/callstack/agent-device/blob/v0.21.18/skills/agent-device/SKILL.md).
Use matching installed help for varying command/API details. Corrective hints
remain subject to scope; they never authorize installation/upload/retargeting.

Follow the [contract's coverage rule](../../../contract.md#interfaces) and
shared policy; current root/helper/session checks remain necessary. Recorded
owned-fixture and fresh-agent coverage is in the
[README](../../../README.md#verification-and-readiness), not a claim about every
app or UI/backend combination.

## Implemented `pi-re device` selection

`pi-re device <agent-device command args>` is the bundled owned-lab interface.
For non-help/version commands it locks the lab, verifies selected owned emulator
identity and root (adb root then UID0), and supplies these upstream arguments:

- `--platform android` and `--serial` for the setup-selected owned emulator.
- `--session` derived from the AVD identity and owner token.
- `--state-dir` pointing to private RE device state.

Caller flags overriding these identities/state are rejected, including alternate
device/UDID/session, remote config, tenant/session lock and Android allowlist.
Do not add them to wrapper examples. The wrapper clears ambient agent-device
settings and disables update notices; state separation is not an ADB privilege
or host sandbox boundary. It does not assume a physical Android device.
Remote/cloud/MCP/web/provider bootstrap remains unavailable in this wrapper.
Help/version commands are offline and bypass root/device contact:

```bash
pi-re device help workflow
pi-re device --version
```

Normal UI commands contact the guest and may root it; they are not no-probe
status reports. Use `pi-re android status --json` for process-only selected-serial
state/root-uninspected. `pi-re frida status` also contacts/verifies the guest.

## Approved automatic helper provisioning

Confirm setup of **this owned emulator lab** is within the requested scope before
opening an app. The first UI snapshot automatically verifies and may deploy/update the
bundled snapshot helper APK; opening can return that first snapshot. This is an
approved provisioning side effect, not a reason for blanket per-command prompting.
Record chosen packaged helper hashes/version, installation/update, permissions,
IME selection/restoration, persistent-helper `adb forward` mappings and residual
state. Text entry may use the bundled IME. Review cleanup/interruption behavior
and record coverage limits. Source-checkout helper builds/arbitrary downloads are not
approved substitutes; missing packaged assets block the operation.

## Small wrapper sequence

After scope/root/helper readiness checks, with package and UI data approved:

```bash
pi-re device open "$PACKAGE" --timeout 10000 --json
pi-re device snapshot --json
pi-re device is visible "$SELECTOR" --json
pi-re device close --json
```

Expected: controlled selected device/session identity, bounded-depth snapshot,
assertion/typed failure and owned close. The wrapper owns command deadlines
(90 seconds for normal UI), private stdout/stderr and a 16 KiB model-visible
output ceiling; oversized output returns partial/truncated artifact references.
Depth does not bound total tree width or sanitize UI content. Keep private
artifacts/result text behind release approval, including diagnostics. Close after
failure only if the run acquired the session; a failed open may be a foreign claim.

**JSON snapshots in this pinned version return bare `node.ref` values such as
`e10`. The CLI requires `@e10`, not `e10`.** Prefix `@` exactly once when converting
JSON `node.ref` to a CLI argument; preserve any `~sN` suffix. Do not confuse the
Node API's `interactions.press` name with choosing an unverified CLI syntax.
The live-qualified CLI action is:

```bash
pi-re device click '@e10' --json
```

Use only the ref from the immediately preceding snapshot; the example number is
not reusable. After failure inspect the wrapper's **stdout artifact** as well as
stderr: upstream typed error JSON and corrective hints may be in stdout while
stderr is empty. Reconcile the current UI before retrying a non-idempotent action.

Use current CLI refs byte-for-byte, e.g. actual `@e12~s4`, for authorized actions with
`--settle`; durable id/label/role selectors for `.ad` replay. Settle/diff is
best-effort; verify a named expectation. `is` takes selectors, not refs.
`fill` clears/types; `type` appends to focus. Never pass credentials via
model-visible CLI arguments. Sparse/truncated trees cannot prove absence;
helper caps at 5000 nodes before scope filtering, API23 occlusion ordering differs.

### Sparse-snapshot recovery

`-i` selects actionable nodes; it can exclude text labels inside a tappable parent.
A shallow `--depth` can omit nested category/navigation descendants even when the
viewport is loaded. Neither result establishes an absent target. If a bounded
interactive/depth-limited snapshot is sparse, take one privately retained
**full-depth, non-interactive** `pi-re device snapshot --json` before image/OCR or
alternate-backend recovery. The returned nodes form a flat list: use `kind`,
`label`, `ref`, and actual bounds/IDs, not an assumed nested `children` schema.
Project only the relevant labels/refs (25 records / 16 KiB / 30 seconds), rather
than cutting semantic depth or printing the full tree. An oversized wrapper reply
returns a private artifact; load that JSON to project the evidence instead of
interpreting its missing inline result as an empty UI. Check snapshot quality and
loading/dialog state; reconcile once under a finite budget before another route.

Direct ADB recovery must use the already verified setup-selected owned serial and
managed SDK, never the first entry of `adb devices` or an unverified ambient ADB.

Sparse semantics permit a fresh selected-emulator screenshot/coordinate fallback
within the named app's navigation scope; record the limitation, verify the viewport
and outcome, and preserve the private image. No extra approval is needed for that
routine fallback. Text-only main models can explicitly select a retained vision-
capable model; file access alone does not establish Flash image support.
Use installed `help screenshot` and `help click` before choosing varying arguments.

## Direct CLI/Node for in-scope work beyond the wrapper

Retain upstream `agent-device open <package> --platform android --serial <serial>
--session <owned-session> --state-dir <owned-state>` for scoped direct work with
verified selection/state ownership. These flags
belong to direct CLI, not wrapper callers. Set managed Node/ADB/helper assets and
`AGENT_DEVICE_NO_UPDATE_NOTIFIER=1`; no `npx @latest` or runtime downloads.

The `agent-device` module exports `createAgentDeviceClient`, `isAgentDeviceError`,
`normalizeAgentDeviceError`, `apps.open`, `capture.snapshot`, `interactions.press/is`,
`sessions.close`, and `devices.capabilities` returning `{device, availableCommands}`.
Use matching installed types to bind serial/session/state/lock explicitly and
owned close in `finally`. The tagged example's iOS-first-device selection is not
RE Android policy. No direct Node harness is bundled by this guide; the CLI
wrapper is implemented. MCP stays off. Web requires Node >=24, Apple macOS/Xcode;
neither backend is qualified by Android tooling.

## Recovery and evidence

Serialize selected-device mutations; reconcile lost responses before retrying
non-idempotent submit/install/replay. Record action/session/flow/hook IDs only with
independently checked Frida/traffic channels. App network dump is not universal
TLS capture. Snapshots/logs/screenshots/replay files stay private until approved.
Close only the controlled owned session; stop a dedicated daemon only after owner
verification using supported help. No global stop, protected-flag override or
foreign stale-claim release from an error hint. Restore approved IME/settings/
mappings and report helpers/root/permissions/files retained; preserve partials.
