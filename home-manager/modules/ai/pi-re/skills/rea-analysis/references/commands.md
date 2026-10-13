# Pinned REA commands

The Nix runtime records exact dependency versions. `pi-re rea --version` and
subcommand `--help` are interface authority. This profile pins REA **6.4.0**, its
verified **Ghidra 12.1.4** (upstream accepts 12.1.x), **64-bit full JDK 21**, and
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
or every operation. Root MCP sessions avoid repeated imports and expose native
navigation, naming, batch decompilation, call graphs and unknown/evidence ledgers
that have no dedicated CLI counterpart. Children use disposable CLI sessions.
Never let another writer reuse the root's project.

Ghidra import controls are explicitly preserved from the caller's environment:
`REA_GHIDRA_LANGUAGE_ID`, `REA_GHIDRA_COMPILER_SPEC_ID`,
`REA_GHIDRA_SEED_FILE` and `REA_GHIDRA_STARTUP_TIMEOUT_MS`. Upstream validates
language/compiler combinations, absolute seed-file identity/format and timeout
bounds. Set them before starting a root session or for one CLI invocation; restart
the root server before changing its import profile. Seeds are caller assertions,
not discovered facts. Executable/plugin paths remain pinned, not ambient.
JavaScript analyses also expose `--max-heap-mb` and `--analysis-timeout-ms`; consult
installed help and retain explicit partial results when a resource budget expires.

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

## Network, browser and process evidence

The wrapper now exposes all 125 non-installer primary/alias CLI routes, including
capability-dependent operations. Command availability is not engine qualification.
The root's matching official skill exposes all advertised MCP tools through
`codemode`, avoiding 170 schemas in every model request. Discover narrowly:

```javascript
return await searchTools("inspect web network capture", { namespace: "mcp__rea", limit: 3 });
```

Use `describeTool()` for the returned name before calling it. MCP results are
`CallToolResult`: check `isError`, then `structuredContent` or `content`. Preserve
Evidence IDs and use summary/paged views rather than printing whole graphs.
CLI `inspect-analysis-view` and `inspect-evidence-bundle` take explicit saved JSON
inputs; they cannot read the root server's in-memory Evidence IDs.

```bash
pi-re rea inspect-web-network-capture "$CAPTURE" har --json
pi-re rea inspect-web-network-capture "$FLOWS" mitmproxy --json
pi-re rea capture-process --help
pi-re rea capture-browser-scenario --help
pi-re rea decode-android-resources --help
```

Saved capture inspection never fetches recorded URLs. Native flow decoding uses
pinned mitmdump 12.2.3; the adapter has a 32 MiB input cap. Keep originals private
and read [traffic](../../web-protocol/references/traffic.md) for release policy.
Browser scenarios use the pinned Chrome executable with an owned profile or an
explicit dedicated loopback CDP endpoint. Passive page inspection/listing does
not launch that endpoint. Browser/process/Electron scenarios can execute targets
and send requests: read the official runtime guide and shared scope policy first.
`observe-web-execution` resets counters and temporarily disables optimization;
it is not passive observation. Do not attach to an ordinary personal browser.

REA ADB requests must select the configured emulator serial. The pinned ADB
transport filters enumeration, rejects other serials and verifies the existing
owned/rooted lab while holding its lifecycle lock; it does not boot/root the
emulator or alter CA/proxy state. Prepare it with `pi-re lab start` first. Reuse
our device/Frida/traffic interfaces for coordinated runtime work.

## Optional engine boundaries

Ghidra, full JDK21, headless JADX, direct JADX/Apktool, ADB, mitmdump and Chrome are
provisioned. PE resources, managed metadata and EVM parsing need no commercial
engine. EVM's resource limiter is pinned for NixOS rather than `/usr/bin/prlimit`.
Some routes remain unavailable until a separate reviewed prerequisite change:

- IDA, Hopper and JEB require proprietary installations/licenses; JEB also needs
  a caller-started local MCP server. Default native provider is pinned Ghidra.
- ELF layout/core diagnostics need pwntools 4.15.0, pyelftools 0.33 and Unicorn
  2.1.2; stock tool presence is not proof of that version combination.
- Firmware needs Binwalk 3.1.x or Unblob 26.6.x plus format extractors.
- JavaScript source recovery needs Wakaru ^1.13.0 (verified 1.14.0).
- Apple UI/signing/runtime tools require macOS; Windows-specific runtime paths
  are not certified on Linux. Opening their portable metadata is separate.

The wrapper strips ambient `REA_*` engine/transport configuration and supplies
reviewed absolute paths, preserving only the explicit Ghidra import controls above. Arbitrary provider installation, engine downloads and upstream `npx/setup`
recovery instructions are replaced by a focused Nix configuration update.

## Provenance and maintenance

The release package, official Ghidra ZIP and Android JAR are fixed-output,
hash-verified Nix dependencies. The runtime lock is a production-only projection
of the exact REA release lock, with unchanged versions and integrity hashes.
Maintainer update provenance lives in `packages/rea/README.md` in the
configuration checkout, which is not a runtime prerequisite. Use installed help
rather than expecting checkout documentation in an investigation folder.

Primary references:
[REA release](https://github.com/morluto/rea/tree/rea-agents-6.4.0),
[Ghidra policy](https://github.com/morluto/rea/blob/rea-agents-6.4.0/src/ghidra/GhidraInstallationPolicy.ts),
[Android provider](https://github.com/morluto/rea/blob/rea-agents-6.4.0/docs/android-analysis.md),
[JavaScript workflows](https://github.com/morluto/rea/blob/rea-agents-6.4.0/docs/javascript-application-workflows.md),
[CLI/MCP inventory](https://github.com/morluto/rea/blob/rea-agents-6.4.0/src/cliCommandNames.ts).
