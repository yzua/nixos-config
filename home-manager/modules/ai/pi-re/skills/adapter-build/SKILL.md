---
name: adapter-build
description: Build a compatible client, mock, semantic adapter or controlled-service gateway from approved protocol evidence and fixture-tested behavior.
---

# Compatible client and adapter build

Deliver tested supported operations/state/failure semantics, reproducible fixtures
and explicit deployment status. Reconstruction belongs in `web-protocol`;
validation of a suspected boundary failure belongs in `finding-validation`.

Read [policy](../re-intake/references/policy.md),
[evidence](../re-intake/references/evidence.md), and
[bounded queries](../re-intake/references/queries.md).
Load [intake](../re-intake/SKILL.md) for new/changed build or deployment scope.

## Prerequisites

- Approved sanitized fixture hashes and evidence-linked operation/state model.
- Explicit desired client/mock/translation/gateway seam and supported behavior.
- Owned project paths, provisioned runtime/dependencies/test runner and one writer.
- Authorized local execution and finite build/test/time/storage budgets.
- Separate live compatibility and deployment permissions if requested.

A copied provider/login profile is not an application secret source. Keep target
and provider credentials out of fixtures/code/config/model-visible commands.
Unknown executable samples/build hooks need an approved whole-process lab boundary.

## Procedure

1. **Choose the contract.** Name operation inputs/outputs, pre/postconditions,
   state/error/retry semantics, exact observed versus inferred fields and gaps.
   Distinguish a capture prototype from client, semantic adapter or HTTP edge.
   Done when supported/unsupported behavior is written and evidence-linked.
2. **Read the interface guide.** Read [adapter and Caddy](references/adapter.md)
   before implementation/configuration. Verify detected runtime/engine/module
   versions and matching help/types; use existing project test commands.
   Done when actual available interfaces and finite budgets are recorded.
3. **Write discriminating fixtures.** Use approved deterministic positive,
   negative/malformed, timeout and state-order cases. Include streaming/WebSocket
   tests only if that behavior is supported, otherwise state the limitation.
   Done when expected outputs/failure semantics are fixed before implementation.
4. **Implement the smallest seam.** Keep protocol semantics in typed application
   code and transport/edge policy explicit. Use provisioned dependencies only.
   Do not promote inferred behavior to a universal upstream contract.
   Done when supported operations have a coherent implementation and test surface.
5. **Run bounded tests.** Execute offline/on owned mock first, checking exits,
   assertions, coverage/errors and cleanup. Any live comparison needs separate
   endpoint/account/rate/redirect authorization. Validate local edge config if used.
   Done when each supported case has pass/fail/blocked evidence and artifact hashes.
6. **Handoff, not implicit deploy.** Return supported behavior, tests, fixtures,
   build/config identity, unknowns and deployment/rollback plan. Actual deploy or
   privileged reload is a separate reviewed action, not a build completion step.
   Done when another operator can reproduce tests without credentials or guessing.

## Smallest useful example

After guide/version/module review, on one owned local Caddyfile:

```bash
caddy adapt --config "$CADDYFILE" --adapter caddyfile > "$PRIVATE_JSON"
caddy validate --config "$CADDYFILE" --adapter caddyfile
```

Expected evidence: adapted JSON hash/warnings and checked validation result.
No server/deployment is started. Validation provisions modules, so configuration
must already be reviewed for file/network/secret side effects. Generated JSON and
diagnostics remain private until approved. Matching help is authority for flags.

The smallest client test is one approved fixture → one operation → explicit
assertion, plus a negative/error case. Use the project's actual test runner;
there is no assumed `pi-re build`/`deploy` command or bundled adapter script.

## Interpretation

Fixture tests prove measured behavior only. A compatible subset is not complete
upstream equivalence; inferred fields and unobserved state transitions remain
unsupported or provisional. A HTTP success is not semantic success.
Auth/session/cookie state, redirects, retry timing, streaming/backpressure and
cancellation can change compatibility; test or disclose them explicitly.

Caddy adapt is syntax translation; validate is provisioning/config evidence,
not target connectivity, semantic translation or deployment authorization.
Host/TLS behavior is version-sensitive. Never disable verification or copy
unmatched proxy header recipes to hide a compatibility failure.

## Cross-domain branches

- New endpoint/state evidence: [web-protocol](../web-protocol/SKILL.md).
- Owned-browser fixture observation: [re-browser](../re-browser/SKILL.md).
- Android runtime counterpart: [android-runtime](../android-runtime/SKILL.md).
- Suspected trust-boundary violation: [finding-validation](../finding-validation/SKILL.md).
- Native format/call semantics: [native-analysis](../native-analysis/SKILL.md).

## Side effects, retry and cleanup

Builds/tests execute code and write outputs/caches; local mocks/edges own ports,
processes and state. Record owner/readiness/deadline before launching. Review
untrusted project scripts instead of running their setup hooks blindly.
No implicit package install, plugins, cloud uploads, CA trust or ACME activation.

Reconcile uncertain stateful requests/reloads before retry; finite attempts and
idempotency are part of the contract. Cancel only verified owned work and retain
partial tests/logs/artifacts. Close owned mocks/contexts/edge processes; never
stop default global admin endpoints or unrelated services.

Escalate new dependencies/runtime, origins/account/credential policy, destructive
migration and deployment. Finish with read resources, tested operation matrix,
fixture/build/config hashes, observed/inferred limitations and residual state.
