---
name: rea-analysis
description: Query native functions/xrefs through pinned REA/Ghidra, inspect Android classes/methods/references, or map JavaScript/Electron applications without executing targets.
---

# REA static analysis

Use **`pi-re rea` through Bash**: the launcher supplies pinned REA, Ghidra,
JDK 21 and the Android engine. No MCP registration or upstream setup is needed.
Read [intake](../re-intake/SKILL.md) for new scope and
[the evidence policy](../re-intake/references/evidence.md) before releasing output.
Read [commands and limits](references/commands.md) before the first query.

## Procedure

1. **Bind the question.** Identify the authorized local artifact, SHA-256 and one
   behavior/function. Retain originals; choose a private derived directory and
   finite query/output/storage budget. Done when identity, question and budget
   are recorded. Bind the exact input path once to a shell variable and reuse it
   across queries rather than retyping store hashes. Static parsing runs on the
   host, not in a sandbox.
2. **Select the branch.** Run `pi-re doctor --json` for installed facts. Native:
   load [native-analysis](../native-analysis/SKILL.md), then use REA with explicit
   `--provider ghidra`. Android: load
   [android-static](../android-static/SKILL.md); use REA for repeated class/method/
   reference navigation, direct JADX/apktool/SDK for resources, signatures, splits
   and smali corroboration. JavaScript/Electron: use static application analysis
   without a native provider. Done when the selected interface and its limits
   match the question.
3. **Query narrowly.** Check installed subcommand help; save JSON privately with
   stderr and exit status separate. Each Bash call has fresh shell state: define
   variables inside that call. Run native queries sequentially and count every
   attempted invocation, including retries, against the query budget. Native first import may take several minutes:
   use a 420-second Bash timeout for a tiny fixture, larger finite budgets only
   when justified. CLI calls have independent engine lifetimes. Done when one
   query has valid evidence or a named failure/partial result.
4. **Follow evidence.** Select a returned symbol/address/class, then inspect that
   function/method or incoming references. Preserve artifact/provider identities,
   address spaces, limitations and errors. Corroborate consequential pseudocode
   against assembly/smali or observed runtime behavior through the existing lab.
   A recovered global initializer is an **initial value**, not an invariant;
   a bounded reference scan cannot prove it never changes. Done when every
   claimed edge is located or explicitly unresolved.
5. **Close and report.** Check command status, unchanged original hash and cleanup
   diagnostics. Retain private Evidence; release only the approved subset. Report
   observations separately from inference, missing coverage and the smallest next
   query. Done when another analyst can locate the claim and remaining state.

## Smallest useful queries

```bash
pi-re rea function "$BINARY" "$FUNCTION" --provider ghidra --json > "$PRIVATE_JSON"
pi-re rea inspect-android-method "$APK" "$CLASS" "$METHOD" --json > "$PRIVATE_JSON"
pi-re rea analyze-javascript-application "$APP_TREE_OR_ASAR" --json > "$PRIVATE_JSON"
```

Each destination is a fresh owned file. `--json` results retain Evidence and
limitations; inspect the actual envelope rather than assuming bare source text.
No result proves runtime equivalence or recovery of original source.

## Recovery and scope

`pi-re rea doctor --provider ghidra --json` probes Java/engine readiness but does
not import a target or repair anything. It is distinct from no-probe `pi-re doctor`.
A missing/mistyped artifact path is an input failure: correct the bound identity
before retrying, rather than labeling it a transient engine error.
An engine failure is an error to diagnose, not permission to run npm, upstream
setup/update, download an engine or select a different provider. Dependencies
are maintained in Nix. Runtime/capture commands remain with the existing scoped
lab/browser workflows. CLI routing excludes package management, MCP and REA
runtime capture; ordinary host Bash is still available under the shared contract.

On timeout, send SIGINT and allow owned cleanup before retrying. Inspect retained
runtime paths or `cleanup_incomplete`; stop only verified owned processes.
Snapshots are caller-selected evidence files, not a promise that a new query
avoids engine startup. Never reuse a Ghidra database with another writer.
