---
name: re-browser
description: Explore an authorized browser page's DOM, console and selected network requests through an available dedicated RE Chrome DevTools CLI instance.
---

# RE browser exploration

Modified derivative of ChromeDevTools' `chrome-devtools-cli` skill at commit
`ae0aaef884c41445d83f86f099ef211f4584b791`. This version replaces global setup,
implicit instance selection and cleanup with RE readiness/evidence/ownership
checks, and narrows recipes to compatible dedicated CLI use. Upstream is **Apache-2.0**, not
MIT; retain [attribution and license](references/attribution.md).

Deliver selected owned-page evidence and reproducible action/request identities.
Protocol modeling belongs in `web-protocol`; scripted tests belong in its
Playwright guide. Ordinary coding/browser resources remain unchanged.

Read [policy](../re-intake/references/policy.md),
[evidence](../re-intake/references/evidence.md), and
[bounded queries](../re-intake/references/queries.md).
Load [intake](../re-intake/SKILL.md) for new/changed browser scope.

## Prerequisites

- Authorized origin/account/navigation/input/observation class and finite budgets.
- Available compatible CLI/browser/runtime combination and dedicated instance.
- Explicit owned daemon endpoint/profile/context/page plan and private artifacts.
- Approved model-visible UI/console/network evidence and provider policy.
- Provisioned telemetry/update policy; no runtime installation/startup repairs.

A page context is not a host sandbox or evidence-release boundary. CLI commands
may start a daemon implicitly; the dedicated-instance gate precedes the first call.
Missing/uncertain daemon separation means blocked, not ambient `list_pages`.

## Procedure

1. **Read readiness.** Read [browser interface](references/browser.md), capability
   facts, installed help and matching source. Verify dedicated daemon/browser
   identity, profile ownership and telemetry/update policy before any tool call.
   Done when the capability is usable or explicitly blocked.
2. **Own a page.** Create an authorized mock/live page in the approved instance;
   record returned page ID, context/profile, run and URL. Existing page lists may
   be used only on that verified instance, not personal browser discovery.
   Done when this run owns an explicit page ID.
3. **Inspect narrowly.** Take a bounded approved snapshot/console/network page.
   Use current snapshot UIDs and explicit page ID. If content may be private,
   capture to private artifacts first and release selected approved material.
   Done when one next action/request target is identified without a bulk dump.
4. **Act and verify.** Perform one authorized navigation/click/fill action with
   current UID, then check an explicit state/request expectation. Record action
   ID/time/window and any failed/partial result. Input/submit may send traffic.
   Done when the observable outcome is evidenced or uncertainty is explicit.
5. **Select evidence.** Page network summaries with `pageSize/pageIdx`, then
   retrieve one request ID/body under private byte/storage limits. Link page,
   request, action/run and artifact hash; never expose all browser history.
   Done when the selected question has evidence and coverage limits.
6. **Close owned state.** Close only this run's pages/contexts; retain private
   evidence. Stop a daemon only if this run owns the dedicated lifecycle and
   readiness/identity still matches. No global stop/uninstall recovery.
   Done when every page/process is closed, intentionally retained or unresolved.

## Smallest useful example

After the dedicated-instance gate, on an approved owned mock:

```bash
chrome-devtools new_page "$MOCK_URL" --output-format=json
chrome-devtools list_network_requests "$PAGE_ID" \
  --pageSize 25 --pageIdx 0 --output-format=json
chrome-devtools close_page "$PAGE_ID"
```

`PAGE_ID` comes from the new-page result, never an assumed index or foreign page.
Expected evidence: created identity, bounded request summaries and checked close.
Save responses privately when they are not approved for model exposure; JSON
mode is not redaction. Read per-command help for version-varying shapes.

This direct CLI recipe does not implement daemon isolation or a browser launcher.
If the installed CLI's dedicated lifecycle cannot be proved, return blocked.

## Interpretation

An accessibility snapshot is selected browser state, not complete DOM/application
coverage. Current UIDs can become stale after navigation/DOM changes.
Missing requests/bodies or console entries can reflect retention/filter/runtime
errors; absence is not proved by an empty or partial query.

Navigation and evaluation can mutate state/send traffic. Screenshots/traces/
console stacks/URLs may contain credentials or personal data. Keep them private
until approved, even when the CLI offers header redaction or file restrictions.

## Cross-domain branches

- Request/state/capture and Playwright tests: [web-protocol](../web-protocol/SKILL.md).
- Candidate failure: [finding-validation](../finding-validation/SKILL.md).
- Compatible client/gateway: [adapter-build](../adapter-build/SKILL.md).
- Android counterpart: [android-runtime](../android-runtime/SKILL.md).

## Retry and escalation

On timeout/lost action response, re-inspect the owned page before retrying.
Non-idempotent submission/download/upload requires reconciliation, not repetition.
Cancel only owned work; preserve partial artifacts. No personal-page attachment,
global daemon restart, runtime browser download or experimental/MCP enablement.

Escalate new origins/accounts, credential/data release, filesystem uploads,
trust changes, unknown ownership or exhausted budgets. Finish with page/profile/
endpoint identity, read guide/version, observed action/request evidence, limits
and cleanup disposition; host/yolo remains explicitly unsandboxed.
