# REA package provenance

This package set supplies `pi-re`'s CLI/root MCP and matching official skill on
Linux x86_64. Only the isolated RE profile loads the bundled upstream skill;
ordinary coding Pi and shared skills.sh installations remain unchanged.

## Pinned artifacts

- **rea-agents 6.5.0**: the compiled official
  [npm artifact](https://registry.npmjs.org/rea-agents/6.5.0), verified against
  registry SHA-512 integrity. The npm release omits `gitHead`; its
  [Sigstore/SLSA provenance](https://registry.npmjs.org/-/npm/v1/attestations/rea-agents@6.5.0)
  binds that digest to release commit `3b79af28e80785afce9f5998d8f03289402a1847`,
  matching tag `rea-agents-6.5.0`. Verification included the signature,
  transparency log, GitHub OIDC issuer and exact release-workflow identity.
  Preserve `dist`, `scripts`, `bridge`, `native`, `third_party`, `licenses` and
  `skills`: runtime resources resolve relative to this layout. The official skill
  is version 42 with 207 advertised MCP tools.
- **package-lock.json**: a runtime-only projection of the
  [release lock](https://github.com/morluto/rea/blob/3b79af28e80785afce9f5998d8f03289402a1847/package-lock.json).
  Delete entries marked `dev`, and remove root `devDependencies` and
  `hasInstallScript`; retain every runtime version, URL and integrity unchanged.
  `importNpmLock` fetches dependencies by upstream integrity. Lifecycle scripts
  stay disabled; compiled dist is used and the Linux PTY addon is auto-patched
  against the Nix compiler runtime. No TypeScript/Gradle build. Optional npm
  Frida 17.23.2 remains unbuilt: its downloader/native installation is not run.
  Incur's notifier is disabled; the launcher also rejects global updater flags.
- **Ghidra 12.1.4**: official
  [release ZIP](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.4_build),
  using its published SHA-256. Override the maintained Nixpkgs binary repack;
  retain matching native components, ELF patching and launch wrappers. REA 6.5.0
  still verifies this build and accepts 12.1.x with limitations. Full JDK21 is
  unchanged.
- **jadx-headless-mcp 0.7.1**: official
  [engine release](https://github.com/1013503897/jadx-headless-mcp/releases/tag/v0.7.1),
  retaining the SHA-256 in REA's
  [release identity](https://github.com/morluto/rea/blob/3b79af28e80785afce9f5998d8f03289402a1847/src/android/JadxRelease.ts).
  This query engine complements direct Nixpkgs JADX/apktool.

The upstream [release run](https://github.com/morluto/rea/actions/runs/38564502044)
has a successful exact-revision qualification gate, but failed its post-publication
check because the runner checkout lacked `dist/catalogIdentity.js`. The published
archive contains that file. MCP Registry publication was skipped. Local package,
MCP and owned-fixture checks remain required; do not describe the entire release
pipeline as green.

## Integrated 6.5 workflows and boundaries

All 151 non-installer primary/alias CLI routes are exposed. The root's persistent
stdio MCP server exposes the full tool catalog through native Pi/codemode;
children remain CLI-only. The official skill and six references are copied
unchanged with MIT attribution. Our adapter overrides upstream installation recipes.

New static workflows include exact JavaScript source selection, retained summary
views, SQLite snapshots, Go/Rust metadata, Flutter/Dart, Electron fuses, Harmony
package graphs and masked Ghidra byte search. Node 24.21.0 from the selected
Nixpkgs satisfies SQLite's stricter Node 24.15+/26+ `DatabaseSync.limits` requirement.
Static metadata and partial coverage never establish runtime equivalence.

Managed absolute paths supply existing Apktool, owned-lab ADB, mitmdump, Chrome,
GNU objdump, TShark/capinfos and resource limiters. Wireshark 4.x is admitted;
selected 4.6.9 differs from upstream's recorded 4.6.6, so test saved captures
locally. No live capture permissions or system services are added.

Deferred engines are explicit: WABT requires 1.0.42 (selected Nixpkgs has 1.0.41),
sigrok-cli requires 0.7.2 (selected Nixpkgs has 0.8.0-unstable), and the optional
Node Frida binding needs a separate native-package/runtime review. Continue using
the existing managed Frida lab. GDB/Rizin/Cutter are not provisioned by this
change; their exposed routes are execution/mutation interfaces, not passive static
inspection. Licensed engines, firmware extractors, pwntools and Wakaru remain
separate prerequisites. No engine is silently downloaded or version-spoofed.

6.5 has schema changes: `get_call_graph.normalized_result` is `{ graph, limitations }`;
runtime attachment/segment/source facts can be null; `binary_session` no longer
repeats the tool catalog; ADB replacement intent is not proof of replacement.
Discover actual MCP schemas and retain unknowns.

## Maintenance and verification

Keep updates focused: verify the npm artifact/tag/provenance, regenerate only the
runtime lock projection, inspect engine requirements, refresh the official skill
and CLI allowlist, then update tests and hashes. Leave `flake.lock` and unrelated
inputs unchanged. Check trusted caches and get approval before substantial local
builds. Never accept a mismatched hash without verifying the intended artifact.

Run offline `python3 -B tests/pi-re-rea.py` and installed Pi loader checks. Build
`pi-re` and `rea-fixture`, then run the opt-in `tests/pi-re-rea-integration.py`
(native/JavaScript/SQLite/objdump and optional owned APK) and
`tests/pi-re-rea-workflows.py` (207-tool MCP inventory, saved HTTP/packet captures,
PTY and optional persistent Ghidra/owned browser). These use no model or real
device. A live agent trial is separate; passing fixtures do not certify arbitrary
binaries, optional engines or real-device acquisition.
