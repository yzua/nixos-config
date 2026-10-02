---
name: web-protocol
description: Reconstruct request operations and state from captures or approved web/API behavior, and distinguish offline inspection from traffic modification or replay.
---

# Web and protocol reconstruction

Deliver an evidence-linked operation/state model and approved sanitized fixtures.
Interactive page control belongs in `re-browser`; compatible implementation
belongs in `adapter-build`; suspected violations belong in `finding-validation`.

Read [policy](../re-intake/references/policy.md),
[evidence](../re-intake/references/evidence.md), and
[bounded queries](../re-intake/references/queries.md).
Use [intake](../re-intake/SKILL.md) for new/changed authorization.

## Prerequisites

- Input capture/hash/format, or approved origin/account/action for live evidence.
- Distinct authorization for observation, capture, mutation and replay.
- Approved model metadata/fixtures and immutable private originals.
- Available compatible capture/reader/browser/runtime capabilities as needed.
- Finite query/capture/request/body/time/rate/concurrency/storage budgets.

A saved flow read is not a live request; an addon may nevertheless send traffic.
A guide is not an installed flow-query adapter. Use installed direct APIs or
write bounded task code when no adapter exists; missing/incompatible dependencies
block that route, not all offline analysis. Apply the shared policy's coverage rule.

## Procedure

1. **Identify the input.** Record capture hash/native versus HAR/PCAP, source,
   time window, tool version and release class. For live work bind origin,
   account, endpoint/browser/device and run owner before connecting.
   Done when every planned evidence source has provenance and permission.
2. **Read the selected guide.** Read [traffic](references/traffic.md) for flows,
   mitmdump/addons/capture/replay. Read [Playwright](references/playwright.md)
   for scripted browser fixtures or protocol-specific branches. Use installed
   help and matching sources; state unavailable modes instead of inventing flags.
   Done when chosen interface and bounds are explicit.
3. **Select before bodies.** Produce at most a bounded summary page, then choose
   one flow/request by identity. Preserve diagnostics, continuation/exhaustion
   and missing/streamed body state. Extract exact bytes privately only when needed.
   Done when a selected operation links to capture/hash/flow/request evidence.
4. **Model one transition.** Record method, origin/path, framing, required state,
   request fields, response/error and state changes. Separate observed bytes
   from inferred names/schema meanings and alternative explanations.
   Done when each modeled property has evidence or an inference label.
5. **Prove minimally.** If replay/modification is authorized, design one bounded
   mock/local experiment and negative control. Live replay is separately gated
   by endpoint/account/rate/redirect authorization; no automatic replay of a file.
   Done when reproduction confirms/rejects a precise property or is blocked.
6. **Release and close.** Preserve private originals; create reviewed sanitized
   fixtures, record hashes/approval, and close only owned captures/pages/tests.
   Restore approved routing/trust changes and report unresolved state.
   Done when the model and its coverage/cleanup can be reproduced from evidence.

## Smallest useful example

For an approved small capture, the traffic guide's direct `FlowReader` loop
selects IDs/method/status under record/scan limits. For an approved owned mock:

```bash
curl --connect-timeout 3 --max-time 10 --max-filesize 16384 \
  --output "$PRIVATE_BODY" --dump-header "$PRIVATE_HEADERS" \
  --write-out '%{http_code}\n' "$MOCK_URL"
```

Expected evidence: curl exit, HTTP status and private byte/header artifact hashes.
The bounded-query guide explains version/streaming limits and redirect policy.
It is not a blanket permission for external traffic or credential-bearing URLs.
Only approved metadata enters model output; body size limits are not redaction.

## Interpretation

A successful request does not prove the inferred schema, complete state machine,
authorization boundary or absence of other endpoints. Missing bodies/responses,
streaming/compression/unknown encodings, corrupt input and request failures remain
explicit. HAR can omit non-HTTP evidence and original flow identity.

A correlation timestamp is not causation. Preserve action/run/flow IDs and clock
relations; repeat only within authorized budgets with a useful control.
Forward/reverse/upstream/WireGuard/local capture require different routing/trust/
privileges; mode switching is not an automatic repair. Keep TLS checks enabled;
use the coordinated guest-only CA path when in scope and record its readiness.
Additional CA/pinning changes are not an automatic repair.

## Cross-domain branches

- Interactive browser: [re-browser](../re-browser/SKILL.md).
- Android routing/root/action: [android-runtime](../android-runtime/SKILL.md).
- Semantic Android UI: [re-device](../re-device/SKILL.md), only if enabled.
- Candidate boundary violation: [finding-validation](../finding-validation/SKILL.md).
- Tested client/mock/gateway: [adapter-build](../adapter-build/SKILL.md).

## Side effects and recovery

Capture may create CA/config files; addons execute host code; replay/navigation/
submit sends traffic; route hooks modify behavior. Record owners and finite
lifetimes before starting. Filters and browser contexts are not network/sandbox
boundaries. Default lab capture semantics follow the
[contract](../../contract.md#open-box-autonomy); optional tools still require
actual availability/compatibility, and MCP remains disabled.

On timeout/lost response, inspect owned state and server outcome before retry.
Non-idempotent actions need reconciliation. Preserve partial captures and errors;
stop only owned listeners/captures/pages, not personal browser/global daemons.
Escalate out-of-scope active origins/accounts, trust changes beyond owned-lab
setup, credential exposure or exhausted budgets; an unseen captured hostname
alone is not an escalation. Finish with observed operations, inferred semantics, fixture release,
versions, partial coverage and cleanup; do not claim a complete API from a sample.
