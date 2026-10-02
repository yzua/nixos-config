---
name: native-analysis
description: Inspect ELF, PE, Mach-O or native libraries for metadata, selected functions, strings and xrefs with build/address-aware Rizin or Ghidra evidence.
---

# Native analysis

Deliver selected native observations with binary/build/address identity and
analysis limits. This is not sample execution, fuzzing or an assumed Ghidra query
service. Read [intake](../re-intake/SKILL.md) for new/changed scope.

Read [policy](../re-intake/references/policy.md),
[evidence](../re-intake/references/evidence.md), and
[bounded queries](../re-intake/references/queries.md).

## Prerequisites

- Approved binary/library artifact and authorized static-analysis class.
- Immutable input hash/build identity and approved model evidence subset.
- Available compatible Rizin/Ghidra and matching bindings/JDK as needed.
- Owned derived directory/project with a single writer.
- Explicit architecture/ABI/base question and finite analysis/storage budget.

Unknown executable samples require an approved whole-process lab boundary before
execution. Host/yolo, a project directory and a device emulator are not a host
sandbox/VM. Static parsing must not invoke extracted code, loaders or build hooks.

## Procedure

1. **Bind the binary.** Record path/provenance/hash/build ID if present, format,
   architecture/endianness and sub-binary selection. Identify whether the question
   concerns file offsets, virtual addresses or runtime module-relative addresses.
   Done when input and address-space identities are explicit.
2. **Read the engine guide.** Read [native tools](references/tools.md), detected
   versions and matching help/API docs. Choose quick metadata before deep analysis.
   Confirm ambient config/plugin policy and any project reuse identity.
   Done when direct engine interface, owner and finite bounds are recorded.
3. **Query narrowly.** Select one metadata category/symbol/address or bounded
   strings. Save bulk engine output privately and emit approved selected evidence.
   Check parser/schema/exit diagnostics, unsupported formats and truncated data.
   Done when the initial question has a qualified location or explicit limitation.
4. **Deepen only if needed.** Import/analyze into an owned Ghidra project on a
   finite budget; reuse only matching checked analysis state. Review task-specific
   function/xref/decompiler export code against installed APIs before execution.
   No bundled native query/export script is assumed.
   Done when selected function evidence and analysis completeness are recorded.
5. **Corroborate.** Relate imports/strings/xrefs/decompiled semantics to bytes and
   addresses. Mark inferred types/control flow and unresolved indirect calls.
   If runtime is needed, load the Frida branch only after rooted selected-lab gates.
   Done when consequential claims have corroboration or a named uncertainty.
6. **Report and close.** Link binary/build hash, loader/base/address space,
   function/symbol, options, export/query revisions and partial diagnostics.
   Close owned pipe/decompiler/project writer; retain private evidence.
   Done when each claim is reproducibly locatable and ownership is reconciled.

## Smallest useful example

After the native guide, on one approved artifact:

```bash
rz-bin -j -I "$BINARY" > "$PRIVATE_META"
rz-bin -j -s -n "$SYMBOL" "$BINARY" > "$PRIVATE_SYMBOL"
```

Expected: checked metadata and selected symbol JSON for reviewed Rizin 0.8.2.
No entire symbol table is required when one known symbol answers the question.
Review selected fields/bytes and release status before model exposure.
If installed flags/schema differ, use matching help/source and report the actual
supported bounded interface; never replace the release silently.

For Ghidra, read the local headless/manual/API branch in the guide before import
or task code. Headless automation is not by itself a paginated evidence service.
A missing exporter is a task-code need, not a blanket block: write a bounded
script using installed APIs, check it on an owned fixture and report partial
coverage under the shared policy. Missing/incompatible engines still block.

## Interpretation

Disassembly/decompilation reconstructs code. A missing symbol, string or xref
cannot establish absence of a behavior under obfuscation, packing, stripping,
indirect calls or incomplete analysis. Decompiler types/names are hypotheses
unless backed by symbols/bytes/ABI context.

Quick metadata is not deep analysis. Headless exit success does not prove all
analyzers/decompilers completed; preserve timeout/partial state and logs.
Fat binaries, PIE/ASLR, loader bases and address spaces must remain explicit.
Never copy a static virtual address into a runtime hook without conversion.

## Cross-domain branches

- Android package/native linkage: [android-static](../android-static/SKILL.md).
- Android dynamic observations: [android-runtime](../android-runtime/SKILL.md).
- Before Frida server/Gadget/hook planning, read the authoritative
  [Frida guide](../android-runtime/references/frida.md); selected root gates first.
- Suspected boundary failure: [finding-validation](../finding-validation/SKILL.md).
- Format/client semantics: [web-protocol](../web-protocol/SKILL.md).

## Side effects, retry and cleanup

Imports/analyzers/scripts mutate projects and consume CPU/storage. One project
writer owns a run; stop on collisions. Verify prior process completion before
reusing a timed-out project. Do not acquire plugins/debug symbols from the network
or switch to absent/disabled MCP/GUI bridges as an automatic repair.

Read-only metadata can have dangerous options: runtime library loading is
execution; debug symbol downloads are traffic. The guide identifies those branches.
Retries use checked owned paths and finite new budgets, preserving failed output.
Cancel owned analysis/pipe processes, dispose decompilers and retain status logs.
Never kill personal Ghidra sessions or open a second writer as recovery.

Finish with read resources, binary/build/address identity, observation versus
inference, qualified locations, partial coverage and cleanup disposition.
