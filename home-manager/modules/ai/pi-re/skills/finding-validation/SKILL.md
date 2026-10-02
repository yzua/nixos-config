---
name: finding-validation
description: Validate a suspected trust-boundary failure or scanner candidate with a falsifiable bounded experiment, local rules and positive/negative controls.
---

# Finding validation

Deliver a candidate/confirmed/rejected/blocked record linked to reproducible
evidence. Scanner matches and inferred vulnerabilities are candidates, not proof.
This workflow is not a license to crawl, scan or exploit an unspecified target.

Read [policy](../re-intake/references/policy.md),
[evidence](../re-intake/references/evidence.md), and
[bounded queries](../re-intake/references/queries.md).
Load [intake](../re-intake/SKILL.md) for missing/changed validation authorization.

## Prerequisites

- Precisely stated candidate/claim and suspected trust boundary.
- Target/build/account/input identity and approved evidence.
- Separate static rule versus live confirmation action classes.
- Finite requests/attempts/time/rate/concurrency/storage and stop conditions.
- Available compatible local engine, or explicit manual/blocked branch.

Host mode is not sandboxed. Prefer owned local fixtures/mocks. Unknown executable
samples require an approved whole-process lab boundary before execution.
Optional active scanner/MCP packs remain unfinished/disabled. Bounded delegation
uses the [root-only Flash interface](../../contract.md#interfaces) within the same
scope; it grants no new testing permission.

## Procedure

1. **Make the claim falsifiable.** Name boundary, prerequisites, affected identity,
   expected violation and an alternative explanation. Separate scanner candidate
   from observed facts and inferred impact.
   Done when an experiment could confirm or reject a specific property.
2. **Bind permission and budget.** Record action class, target/account, finite
   attempts and stop conditions before testing. Static source rules do not imply
   live replay or active testing permission. Escalate new classes/scope once.
   Done when every experiment/control is authorized or blocked explicitly.
3. **Read the validation guide.** Read [local validation](references/semgrep.md)
   before Semgrep/rule work. Confirm installed help, local rule hash, engine/
   parser/edition, telemetry/version-check policy and extraction coverage.
   Done when the actual bounded interface and limitations are known.
4. **Design controls.** Specify a minimal positive case, negative case and how
   diagnostics distinguish a failure from a clean result. Use offline/mock cases
   first when they can answer the question; read the domain skill for live proof.
   Done when expected outputs/coverage are fixed before execution.
5. **Run and reconcile.** Execute within budget; check exits, parsing/skips,
   timeouts and partial outputs. Record exact inputs/rules/test code and side
   effects. Inspect uncertain mutation outcomes before any retry.
   Done when controls and claim have evidence or explicit blocked/error status.
6. **Classify.** Confirm only the tested boundary under recorded prerequisites;
   reject only within measured coverage. Otherwise keep candidate or blocked.
   Preserve alternatives, sanitized reproduction, limitations and cleanup.
   Done when the result can be audited without treating scanner output as truth.

## Smallest useful example

On an approved local source fixture and reviewed local rule, after guide/help:

```bash
SEMGREP_SEND_METRICS=off SEMGREP_ENABLE_VERSION_CHECK=0 \
  semgrep scan --config "$LOCAL_RULE" --json --metrics off \
  --timeout 5 --max-target-bytes 100000 --jobs 1 "$SOURCE" \
  > "$PRIVATE_RESULT"
```

Expected evidence: rule/location candidates plus diagnostic and scanned/skipped
coverage, checked exit and rule/input hashes. JSON stays private pending release.
The guide requires flag verification for the installed version and a finite
overall deadline. No local rule/fixture/test script is bundled or presumed.
An unavailable engine blocks that capability, not approved manual reasoning.

The smallest confirmation is one owned fixture showing the claimed distinction
and a negative control showing it is not merely a normal error. Live traffic
needs separately recorded endpoint/account/budget authorization before execution.

## Interpretation

A clean scan cannot establish safety: rule coverage, parser/extraction failures,
ignored files, unsupported languages and edition differences matter.
Decompiled source is not a complete original source model. A successful
exploit-looking response can be ordinary behavior, cached state or a failed
measurement; controls and independent boundary evidence decide the claim.

Do not upgrade a candidate on severity language, tool confidence or a single
ambiguous screenshot. Distinguish observed impact from inferred wider impact.
Unknown/partial results remain partial. Confirmation is not authorization for
broader enumeration, persistence, data extraction or deployment.

## Cross-domain proof

- Android static location: [android-static](../android-static/SKILL.md).
- Selected rooted device observation: [android-runtime](../android-runtime/SKILL.md).
- Request/replay evidence: [web-protocol](../web-protocol/SKILL.md).
- Owned-page exploration: [re-browser](../re-browser/SKILL.md).
- Native function/ABI: [native-analysis](../native-analysis/SKILL.md).
- Fix/mock/client contract: [adapter-build](../adapter-build/SKILL.md).

Read the domain guide at the proof branch, not after execution.

## Side effects and recovery

Local scan writes result/cache files; live tests can change target state or send
traffic. Optional scanners/templates may execute code or contact third parties.
No auto registry configuration, autofix, upload, package install or implicit
remote scanner fallback belongs in this workflow.

Retry only finite authorized cases whose idempotency/outcome is checked. Stop on
unexpected destinations, credential exposure, identity drift or exhausted budget.
Cancel only owned work; preserve candidate/raw/partial evidence before cleanup.
Finish with status, claim/boundary, controls, evidence hashes/locations, read
resources, tool/rule versions, coverage and residual state.
