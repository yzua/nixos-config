---
name: android-static
description: Inspect Android APK classes/methods/references with REA, and manifest/resources, signatures, splits or DEX with direct JADX/apktool/SDK corroboration.
---

# Android static analysis

Deliver hash-qualified manifest/resource/code locations and decompilation limits.
This workflow inspects artifacts; it does not rebuild, sign, install or execute
an app. For a new input or changed permission load
[re-intake](../re-intake/SKILL.md) first.

Read [policy](../re-intake/references/policy.md),
[evidence](../re-intake/references/evidence.md), and
[bounded queries](../re-intake/references/queries.md).

## Prerequisites

- Authorized static-inspection class and objective bounded to one behavior.
- Approved model inputs; immutable originals and fresh owned derived directory.
- Every APK/split/DEX input identified by path/provenance/hash.
- Available compatible JADX/apktool/SDK combination, or a stated blocked subset.
- Finite analysis/storage deadline and explicit host/lab exposure choice.

A rooted device is required for runtime work, not for offline APK/DEX inspection.
Do not contact a device to fill a missing static input. Ask for an approved
artifact/acquisition scope or continue on the approved inputs with limits.

## Procedure

1. **Inventory inputs.** Hash base/splits/DEX; record supplied package/version/
   signature metadata and missing split roles. Verify available SDK inspection
   metadata without executing extracted code.
   Done when input identity and incomplete-set limitations are recorded.
2. **Read the engine guide.** Read [static tools](references/tools.md), detected
   versions and matching installed help. For repeated class/method/reference
   queries load [rea-analysis](../rea-analysis/SKILL.md) and its command guide.
   Select direct source/resource/smali export for corroboration or unsupported
   REA subsets; avoid whole-app dumps when a class/file answers it.
   Done when chosen direct API and finite import/output budgets are recorded.
3. **Decode selectively.** Use REA for one class/method or JADX for a selected
   class export, apktool for needed
   resource/smali corroboration. Export into fresh owned paths; keep diagnostics
   separate. Do not infer that a failed export means code is absent.
   Done when exports exist, exits/diagnostics are checked, and status is explicit.
4. **Trace one behavior.** Query selected files with literal terms/signatures;
   follow a finite number of callers/callees/resources. Record each important
   class/method/resource and which artifact owns it.
   Done when the claimed path has location evidence or a named unresolved edge.
5. **Corroborate.** Confirm a consequential decompiled claim against smali/DEX,
   manifest or resource bytes. Label reflection, dynamic/native behavior and
   reconstruction as inference. Read `native-analysis` for ELF/native edges.
   Done when each consequential claim has corroboration or a coverage caveat.
6. **Report.** Link hashes, class + method signature, selected file/line/offset,
   tool versions/options and decompilation failures. Identify the smallest next
   runtime experiment without performing it under static permission.
   Done when another analyst can locate every claimed observation.

## Smallest useful example

After reading the guide, choose one approved APK and fully qualified class:

```bash
jadx --single-class "$CLASS" --single-class-output "$JAVA_OUT" "$APK"
```

Expected evidence: selected class export, checked diagnostics and qualified
class/method location. This is a direct JADX 1.5.6 interface, not a custom
`pi-re` query command. The output shape/path must match installed help.
If this flag is unavailable, report incompatible/blocked selective export;
propose a bounded supported alternative rather than switching releases.

If the question is a manifest/resource behavior, use the direct apktool/SDK
branch in the guide and emit only the selected approved XML/text portion.
JSON is optional: stable source/smali/XML with hashes and locations is valid.

## Interpretation

Decompiled Java is a reconstruction. Source line numbers, apparent method names,
missing call edges and comments are not guaranteed original-source facts.
Static permissions/exported components/trust declarations are hypotheses about
runtime behavior until the relevant version/device path is observed.

Base-only inspection cannot establish split completeness. Bare DEX cannot
establish APK signature, resource state or installed package behavior.
Unresolved frameworks, corrupt archives, parser errors, skipped DEX and native
calls must appear as partial coverage. No matching search term proves only that
term was not found in the successfully inspected bounded files.

## Cross-domain branches

- Native library/call edge: [native-analysis](../native-analysis/SKILL.md).
- Device behavior/trust/dynamic loading: [android-runtime](../android-runtime/SKILL.md).
- Endpoint/request reconstruction: [web-protocol](../web-protocol/SKILL.md).
- Suspected boundary failure: [finding-validation](../finding-validation/SKILL.md).
- Compatible client from approved fixtures: [adapter-build](../adapter-build/SKILL.md).

## Side effects, retry and cleanup

Decoding writes derived files and may use tool caches/framework state; isolate
owned state and verify output collisions before running. Static permission does
not authorize apktool framework installation, rebuild/sign/install or uploads.
No silent dependency/plugins/MCP installation follows a decompilation error.

Retry only into a checked owned directory, preserving original/failed output
provenance. Set a finite new budget and explain the change. On interruption,
check owned analysis processes and partial exports before retrying.
Cancel/stop only owned work. Retain evidence and remove disposable derived
copies only under the retention policy.

Finish with observations, inferences, input/export hashes, versions, partial
failures, read guide, next bounded question and remaining state. Do not claim
runtime confirmation from static code alone.
