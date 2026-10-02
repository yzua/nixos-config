---
name: android-runtime
description: Observe rooted Android lab behavior, correlate selected-device actions/logs/traffic, or write bounded Java/native Frida instrumentation.
---

# Android runtime analysis

Deliver a bounded selected-device observation linked to an action and app/build.
Transport/root readiness belongs here; semantic UI belongs in `re-device`,
traffic reconstruction in `web-protocol`, and APK decoding in `android-static`.

For coordinated boot/root/capture/system-CA/proxy/Frida provisioning or owned
end-to-end checks, first read [coordinated lab](references/lab.md). It documents
capture modes, boot-scoped API35 trust, cleanup and pinned Java bridge usage.

Read [policy](../re-intake/references/policy.md),
[evidence](../re-intake/references/evidence.md), and
[bounded queries](../re-intake/references/queries.md).
Load [intake](../re-intake/SKILL.md) for missing/changed authorization.

## Prerequisites

- Authorized behavior/instrumentation/capture action classes and target account.
- Approved model evidence and finite observation/time/storage/message budgets.
- Explicit selected Android lab serial, package/build and owned run identity.
- Emulator first; verified rooted Android required for this runtime environment.
- Available compatible transport; Frida/UI/traffic coverage checked independently.

Host/yolo is not a sandbox/VM. Unknown sample execution requires a separately
approved whole-process lab boundary. A rooted emulator is not host isolation.
No selected device/root means blocked runtime, not automatic setup.

## Procedure

1. **Bind the device.** Read [selected lab](references/device.md). Use read-only
   `pi-re android status --json`: process-only, setup-selected owned serial, no
   caller serial flag or ADB probe. Record ownership/state; root is uninspected.
   Done when exactly one authorized device/run is identified, or blocked.
2. **Prepare only approved state.** If lifecycle/root provisioning is authorized,
   use implemented `create/start/root` with installed help and finite readiness
   budget. Root requires `adb root` followed by same-serial UID0 verification.
   Record every mutation; profile init does not create a lab. Apply the shared
   policy's capability interpretation, not a blanket qualification gate.
   Done when required readiness/root is verified or the operation is blocked.
3. **Select evidence channel.** Choose bounded ADB diagnostics, Frida,
   semantic UI or independent capture. Read [Frida](references/frida.md)
   before any server/Gadget path or binding operation; root is checked first.
   Prefer bundled ownership routes for lab/server/device lifecycle; use installed
   CLI/Python and scoped scripts for instrumentation beyond the native probe.
   Load UI/traffic skills at their branch. Done when channel identity, compatibility
   and tested versus experimental coverage are recorded.
4. **Observe one action.** Record baseline, action ID, time window/clock relation,
   package/PID and expected observable; run one authorized action with selected
   evidence fields. Save logs/messages/screenshots privately, including errors.
   Done when the bounded window completed or timeout/partial status is explicit.
5. **Correlate carefully.** Relate action to message/log/flow locations. Confirm
   package/PID/transport identity, missing events and clock offsets. Distinguish
   observed sequence from inferred causation; use a negative control when needed.
   Done when the claimed result has evidence and named alternatives/limits.
6. **Detach and restore.** Unload scripts/detach, close owned UI/capture, remove
   owned forwards and restore approved state. Stop owned server/emulator only
   when appropriate. Preserve raw evidence and record residual helper/root state.
   Done when each resource is stopped, retained intentionally, or unresolved.

## Smallest useful example

For the requested owned lab, after the device/Frida guides and current
root/server compatibility checks:

```bash
pi-re android status --json
pi-re android root --json
pi-re frida run --package "$RUNNING_PROCESS"
```

Status is process-only/root-uninspected; root is a separate verified mutation.
Frida setup must already have provisioned the matched pinned Android x86_64 server.
Run attaches only to an existing process, bounded to 30 seconds, returning messages
and default native RPC evidence. It never spawns or provides default Java hooks.
Frida status is a live guest/root-verification operation, unlike Android status.

Use the guide's direct CLI/Python APIs for bounded in-scope hooks. Bare wrapper
`--script` JS has no implicit Java bridge; use the installed pinned CLI or load
its bundled bridge explicitly through Python. Record errors and partial evidence;
no bridge download is needed.

## Interpretation

A log or hook message proves an observation at that point, not complete coverage.
Empty capture can reflect missing trust/routing, app logging, late attach,
wrong PID/class loader, streaming bodies or a failed hook. Check diagnostic and
partial status before interpreting a negative result.

Root does not establish ABI/server compatibility, TLS trust, pinning bypass or
semantic UI readiness. Frida core/server/Gadget must match; tools and Frida 17
bridges need explicit compatibility and coverage checks. Runtime modification can
alter the behavior being studied; preserve baseline and side effects in the result.

## Cross-domain branches

- Selected code/manifest location: [android-static](../android-static/SKILL.md).
- Semantic UI: [re-device](../re-device/SKILL.md); verify owned root and bundled
  helper readiness before opening. First snapshot can auto-deploy helpers;
  record helper/IME/mapping changes.
- Capture/replay/trust: [web-protocol](../web-protocol/SKILL.md).
- Native address/ABI: [native-analysis](../native-analysis/SKILL.md).
- Candidate trust-boundary failure: [finding-validation](../finding-validation/SKILL.md).

## Retry, cancellation and escalation

Serialize device mutations. On a lost response, inspect selected owned state
before retry; submit/install/direct-API spawn may already have happened. Do not replay
non-idempotent actions blindly. Cancellation detaches instrumentation and stops
verified owned work; never kill a target merely because an attach timed out.

Escalate permissions or installs outside the requested owned-lab setup, pinning
bypass/other trust expansion, destructive reset, foreign claims, identity drift
and budget exhaustion.
Do not use `adb kill-server`, global daemon stops or personal-device cleanup.
Finish with selected identity/root evidence, read guides, bounded observation,
versions, partial errors, released artifact references and cleanup disposition.
