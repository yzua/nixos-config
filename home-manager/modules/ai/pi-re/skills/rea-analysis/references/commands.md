# Pinned REA commands

The Nix runtime records exact dependency versions. `pi-re rea --version` and
subcommand `--help` are interface authority. This profile pins REA **6.8.0**, its
verified **Ghidra 12.1.4** (upstream accepts 12.1.x), **64-bit full JDK 21**, and
**jadx-headless-mcp 0.7.1**. Linux native support here is x86_64.
The maintained CLI entry point is `pi-re rea`; it is also available to children.
The REA-local official Node 24.22.1 runtime satisfies its engine and SQLite limits
requirements without changing other applications' Node runtimes.

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
MCP `analyze_function` defaults to a retained summary in 6.8: use its
`normalized_result.parent_evidence_id` for pages, or `detail: "complete"` for an
inline dossier. CLI `function` keeps its complete default; a summary requires an
explicit private `--evidence_output`. `decompile-all` supports resumable directory
exports; `match-native-functions` compares supplied procedure Evidence, not raw
binaries. Read help/schemas before choosing identities and output paths.
Never let another writer reuse the root's project. Call-graph Evidence
uses `normalized_result.graph` plus `normalized_result.limitations`; nullable
attachment/segment/source facts remain unknown. Discover the server catalog with
`tools/list`, not the removed `binary_session.server_identity.catalog.tools`.

Ghidra import controls are explicitly preserved from the caller's environment:
`REA_GHIDRA_LANGUAGE_ID`, `REA_GHIDRA_COMPILER_SPEC_ID`,
`REA_GHIDRA_SEED_FILE`, `REA_GHIDRA_STARTUP_TIMEOUT_MS` and
`REA_GHIDRA_DISABLED_ANALYZERS` and `REA_GHIDRA_DECOMPILE_TIMEOUT_SECONDS`.
Upstream validates language/compiler combinations,
seed-file identity/format, timeout bounds and analyzer names. Disabled analyzers
change coverage and are recorded in the analysis profile. Set them before starting a root session or for one CLI invocation; restart
the root server before changing its import profile. Seeds are caller assertions,
not discovered facts. Executable/plugin paths remain pinned, not ambient.
JavaScript analyses also expose `--max-heap-mb` and `--analysis-timeout-ms`; consult
installed help and retain explicit partial results when a resource budget expires.

`search-bytes` searches initialized provider memory with hex pairs and `??`
wildcards, optional bit masks and returned continuation cursors. It is not raw-file
search. Raw inputs require explicit `--target-format raw-binary`, admitted
`--architecture` and `--entry-point`; never infer an architecture from bytes alone.

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
this static graph. Repeat `--source-path` with exact inventoried paths relative to
the application root to limit source analysis. Imports outside that selection
retain identity/unknown coverage; they are not implicitly analyzed. Selection
changes coverage; summary delivery only changes the view of retained Evidence.
`inspect-electron-fuses` reads packaged fuse bytes without launching the app.

## Other offline artifacts

6.8 adds `inspect-native-exports`, PE imports/certificates/load configuration,
ELF notes/kernel modules, byte entropy, IL2CPP, CPython pyc, Erlang BEAM,
GGUF/safetensors and GPU code-object metadata. Existing artifact inspection and
extraction support Godot PCK, PyInstaller and Node SEA. These bounded readers do
not execute targets or establish complete recovery, signature trust or runtime
registration. `inspect-desktop-application` inventories supported installation
layouts. Discover exact inputs/coverage in installed help or MCP schemas.

- `inspect-sqlite-database "$DATABASE" --table "$TABLE" --column "$COLUMN" --json`
  reads selected ordinary-table rows; omit `--table` for schema inventory only.
  Use a consistent offline database/WAL snapshot; copying a live pair is not proof
  of atomicity. Node 24.15+ in the 24.x line or 26+ with `DatabaseSync.limits` is
  required; the managed runtime satisfies this.
- `inspect-go-binary` inspects embedded build metadata. `inspect-rust-binary`
  inspects cargo-auditable dependency metadata; its absence does not establish
  dependency absence.
- `identify-flutter-build` and `inspect-dart-aot` inspect supported APK/AOT metadata
  without an external engine. Pool semantics and arbitrary APK coverage remain
  partial. `project-harmony-application-graph` inventories supported Harmony
  packages without executing them.
- `inspect-with-objdump "$BINARY" symbols --json` uses managed GNU objdump. Other
  operation names are in help. Following external DWARF links is explicit and
  those external bytes are not bound to the target's Evidence identity.

## Network, browser and process evidence

The wrapper now exposes all 173 non-installer primary/alias CLI routes, including
capability-dependent operations. Command availability is not engine qualification.
The root's matching official skill exposes all advertised MCP tools through
`codemode`, avoiding 229 schemas in every model request. Discover narrowly:

```javascript
return await searchTools("inspect web network capture", { namespace: "mcp__rea", limit: 3 });
```

Use `describeTool()` for the returned name before calling it. MCP results are
`CallToolResult`: check `isError`, then `structuredContent` or `content`. Preserve
Evidence IDs and use summary/paged views rather than printing whole graphs.
CLI `inspect-analysis-view` and `inspect-evidence-bundle` take explicit saved JSON
inputs; they cannot read the root server's in-memory Evidence IDs. Expanded
summary/page views cover supported inventory, WASM, managed, Android manifest,
Dart AOT, Mach-O, EVM and network Evidence. Read actual schemas to select a view;
retain the original Evidence and its coverage even when delivering a compact view.
On failures, preserve retained completed Evidence and partial observations before
retrying or shutting down the server.

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

Saved HTTP capture inspection additionally supports bounded SAZ and supported
aioquic 1.5.0 JSON qlog 0.3 inputs; other qlog layouts remain unsupported. Inferred
HAR method/origin/path-template API surfaces and query-parameter names are
observations/inferences, not proof of server behavior or authorization.

For saved PCAP/PCAPNG, use `inspect-packet-capture` for selected fields/filters and
bounded matching pages; `inspect-packet-fields` discovers installed definitions.
`inspect-pcap-client` reports the selected TShark/capinfos installation and
`inspect-pcap-capture` summarizes endpoints/DNS/SNI/protocols. Managed Wireshark
4.6.9 satisfies the admitted 4.x profile but differs from upstream's recorded
4.6.6. Both packet adapters use pinned `prlimit`; no live packet capture, hardware
acquisition or extra capture privileges are configured. Keep packet payloads private.

`inspect-apk-signature` reads signing declarations without establishing trust;
resource decoding supports repeatable `--locales` for multiple tables. Structured
manifest components and static-final DEX values retain coverage/unknown facts.
`REA_JADX_OPERATION_TIMEOUT_MS` is preserved for a bounded operation deadline;
it does not change the bridge startup handshake.

REA ADB requests must select the configured emulator serial. The pinned ADB
transport filters enumeration, rejects other serials and verifies the existing
owned/rooted lab while holding its lifecycle lock; it does not boot/root the
emulator or alter CA/proxy state. Prepare it with `pi-re lab start` first. Reuse
our device/Frida/traffic interfaces for coordinated runtime work.

## Capture-derived environments and recovery

`environment-build`, `environment-export`, `environment-serve` and
`environment-compare` are exposed. Read the bundled upstream environment guide
before use: builds accept supported HAR/capture Evidence, exports can contain
response bodies, and serving opens an owned listener. Derived-state reads and
recording-supported writes are not a complete application clone. Scope the private
inputs, output disclosure, endpoint and cleanup; use `--replay-only` for stateless
replay. Root MCP exposes environment bundle export through its actual schema.

MCP `inspect_analysis_settings` / `update_analysis_settings` expose bounded
runtime deadlines, admission sizes and worker heaps. Changes affect new work,
survive target close/open and disappear when REA restarts. Explicit call arguments
win; these settings do not raise host or client transport limits. The launcher
also preserves `REA_MCP_INPUT_SCHEMA_PROFILE` (`compact` default or `full`) and
`REA_REFERENCE_SECRET_PATTERNS_JSON` (reference-source path exclusions). Engine,
plugin and transport paths remain managed; other ambient `REA_*` settings are
stripped. Raising transport response ceilings needs a separate client review.

6.6–6.8 changed Evidence coverage and nullable facts; regenerate old snapshots
rather than assuming saved-file migration. ADB version codes are decimal strings.
JSONL output is collection rows followed by a `$rea: "jsonl/v1"` metadata record;
use JSON for whole documents. Reconstruction proofs need implementation/revision
bindings and individual claim outcomes. Preserve unknowns in browser timestamps,
accessibility values and native bindings. Historical browser storage comparisons
need fresh captures on both sides. The official skill/schema is authority.

Process captures in this release can retain sensitive terminal echoes despite
sensitive input markers. Avoid real secrets in recordings; the upstream echo
redaction fix is not in published 6.8. R8 mapping/JNI linking and additional
firmware readers on upstream main are likewise not part of this pin.

## Optional engine boundaries

Ghidra, full JDK21, headless JADX, direct JADX/Apktool, ADB, mitmdump and Chrome are
provisioned, along with TShark/capinfos and GNU objdump. PE resources, managed
metadata and EVM parsing need no commercial
engine. EVM's resource limiter is pinned for NixOS rather than `/usr/bin/prlimit`.
Some routes remain unavailable until a separate reviewed prerequisite change:

- Kuna needs a separately reviewed caller installation/provider selection.
  Optional NativeAOT Ghidra plugins are not provisioned.
- IDA, Hopper and JEB require proprietary installations/licenses; JEB also needs
  a caller-started local MCP server. Default native provider is pinned Ghidra.
- ELF layout/core diagnostics need pwntools 4.15.0, pyelftools 0.33 and Unicorn
  2.1.2; stock tool presence is not proof of that version combination.
- Firmware needs Binwalk 3.1.x or Unblob 26.6.x plus format extractors.
- JavaScript source recovery needs Wakaru ^1.13.0 (verified 1.14.0).
- WABT inspection requires 1.0.42; selected Nixpkgs 1.0.41 is not wired. Comparing
  two complete saved WASM inspection Evidence records needs no active WABT.
- Signal decoding requires sigrok-cli 0.7.2 with libsigrokdecode and Linux prlimit;
  selected Nixpkgs 0.8.0-unstable is not wired. This decodes recordings, not hardware.
- REA's optional Node Frida 17.23.2 binding is not built. Use the existing managed
  Frida lab; REA's generic remote selector does not inherit our device guards.
- GDB/Rizin/Cutter are not provisioned by this integration. Their debugger/command
  routes can execute code, mutate state and leave inferiors running; use only with
  explicit ownership, execution authorization and verified cleanup.
- Apple UI/signing/runtime tools require macOS; Windows-specific runtime paths
  are not certified on Linux. Opening their portable metadata is separate.

The wrapper strips ambient `REA_*` engine/transport configuration and supplies
reviewed absolute paths, preserving only the explicit analysis/schema/exclusion controls above. Arbitrary provider installation, engine downloads and upstream `npx/setup`
recovery instructions are replaced by a focused Nix configuration update.

## Provenance and maintenance

The release package, official Ghidra ZIP and Android JAR are fixed-output,
hash-verified Nix dependencies. The runtime lock is a production-only projection
of the exact REA release lock, with unchanged versions and integrity hashes.
Maintainer update provenance lives in `packages/rea/README.md` in the
configuration checkout, which is not a runtime prerequisite. Use installed help
rather than expecting checkout documentation in an investigation folder.

Primary references:
[REA release](https://github.com/morluto/rea/tree/rea-agents-6.8.0),
[Ghidra policy](https://github.com/morluto/rea/blob/rea-agents-6.8.0/src/ghidra/GhidraInstallationPolicy.ts),
[Android provider](https://github.com/morluto/rea/blob/rea-agents-6.8.0/docs/android-analysis.md),
[JavaScript workflows](https://github.com/morluto/rea/blob/rea-agents-6.8.0/docs/javascript-application-workflows.md),
[CLI/MCP inventory](https://github.com/morluto/rea/blob/rea-agents-6.8.0/src/cliCommandNames.ts),
[Packet capture guide](https://github.com/morluto/rea/blob/rea-agents-6.8.0/docs/packet-captures.md).
