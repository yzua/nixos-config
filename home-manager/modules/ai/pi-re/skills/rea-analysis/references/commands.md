# Pinned REA commands

The Nix runtime records exact dependency versions. `pi-re rea --version` and
subcommand `--help` are interface authority. This profile pins REA **4.1.0**, its
exact supported **Ghidra 12.1.4**, **64-bit full JDK 21**, and
**jadx-headless-mcp 0.7.1**. Linux native support here is x86_64.
The maintained CLI entry point is `pi-re rea`; it is also available to children.

## Native binaries / Android `.so`

```bash
pi-re rea providers --json
pi-re rea doctor --provider ghidra --json
pi-re rea analyze "$BINARY" --provider ghidra --json
pi-re rea search "$BINARY" "$LITERAL" --kind strings --provider ghidra --json
pi-re rea search "$BINARY" "$NAME" --kind procedures --provider ghidra --json
pi-re rea function "$BINARY" "$NAME_OR_ADDRESS" --provider ghidra --json
pi-re rea instructions "$BINARY" "$NAME_OR_ADDRESS" --provider ghidra --json
pi-re rea decompile "$BINARY" "$NAME_OR_ADDRESS" --provider ghidra --json
pi-re rea xrefs "$BINARY" "$RETURNED_ADDRESS" --provider ghidra --json
```

Function dossiers combine pseudocode, assembly, calls and references. Use a
returned qualified symbol or canonical address; virtual addresses are not file
offsets or runtime hook addresses. `xrefs` returns incoming static references,
not observed calls. Strings are analyzed data strings, not all printable bytes.
Missing indirect calls, stripped names and partial analysis remain unknown.
`search` defaults to literal substring matching; `--mode regex` is explicit.
Search/xref results are not paginated: save broad output privately and bound what
is read into the model. `instructions` avoids per-function decompilation, but
still imports and analyzes the target.

Each CLI invocation has its own temporary Ghidra project and closes it. Original
bytes remain unchanged. The first import can be slow; do not use a 30-second
shell deadline and interpret that timeout as an invalid binary. Successful exit
can still contain partial evidence. A cancelled caller does not prove cleanup.

For snapshots, consult that command's help and select an existing private parent
for `--snapshot`. REA validates target/provider/query identities and writes atomic
owner-only evidence. Do not assume a snapshot caches the whole imported program
or every operation. The profile intentionally uses CLI rather than a persistent
MCP session; repeated native queries can incur reimport cost.

## Android APK queries

```bash
pi-re rea inspect-android-package "$APK" --json
pi-re rea search-android-classes "$APK" "$CLASS_TERM" --json
pi-re rea inspect-android-class "$APK" "$CLASS" --json
pi-re rea inspect-android-method "$APK" "$CLASS" "$METHOD" --json
pi-re rea inspect-android-method "$APK" "$CLASS" "$METHOD" --overload-index 1 --json
pi-re rea trace-android-references "$APK" "$CLASS" --method-name "$METHOD" --json
```

Inspect the class inventory to choose an overload; indices are artifact/engine
local, not stable cross-build identities. Incoming references are static provider
relationships. Exact DEX descriptors and instruction offsets are not supplied.
Java/smali text is a derived representation; fallback, truncation and missing
bodies must be reported. Android engine calls have an internal 120-second budget;
allow startup and cleanup in the outer deadline.

This branch does not verify signatures, handle split sets/AAB, decode complete
resource semantics, analyze embedded native libraries or run the app. Use direct
apktool/SDK/JADX from [Android tools](../../android-static/references/tools.md)
for those static subsets; extract a selected `.so` into an owned path and use the
native branch. Runtime goes through the existing rooted device/Frida/traffic lab.

## JavaScript / Electron

```bash
pi-re rea analyze-javascript-application "$APP_TREE_OR_ASAR" --json
```

This maps modules/imports, source maps, routes, IPC, storage and native add-ons
without executing extracted modules. Generic `analyze` also routes directory/
ASAR inputs here only when no provider is forced. Use the explicit command to
avoid ambiguity. Dynamic relationships and unavailable dependencies remain
unresolved. Feature tracing accepts a structured Evidence request; read
`pi-re rea trace-application-feature --help` and the actual analysis result first.
Browser observation/runtime capture is a separate workflow, not established by
this static graph.

## Provenance and maintenance

The release package, official Ghidra ZIP and Android JAR are fixed-output,
hash-verified Nix dependencies. The runtime lock is a production-only projection
of the exact REA release lock, with unchanged versions and integrity hashes.
Maintainer update provenance lives in `packages/rea/README.md` in the
configuration checkout, which is not a runtime prerequisite. Use installed help
rather than expecting checkout documentation in an investigation folder.

Primary references:
[REA release](https://github.com/morluto/rea/tree/rea-agents-4.1.0),
[Ghidra installation probe](https://github.com/morluto/rea/blob/rea-agents-4.1.0/src/ghidra/GhidraInstallation.ts),
[Android provider](https://github.com/morluto/rea/blob/rea-agents-4.1.0/docs/android-analysis.md),
[JavaScript workflows](https://github.com/morluto/rea/blob/rea-agents-4.1.0/docs/javascript-application-workflows.md).
