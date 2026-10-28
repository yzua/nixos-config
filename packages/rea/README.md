# REA package provenance

This package set supplies `pi-re`'s CLI/root MCP and matching official skill on
Linux x86_64. Only the isolated RE profile loads the bundled upstream skill;
ordinary coding Pi and shared skills.sh installations remain unchanged.

## Pinned artifacts

- **rea-agents 6.8.0**: compiled official
  [npm artifact](https://registry.npmjs.org/rea-agents/6.8.0), SHA-512
  `9QDeRnGqEDzABZyr04eLnBXBv/c6I9/TWu/6M0MD4pEfkySI/BIgwTODIbAReX3C1x6hjw9+Jlx4A2yUSPZ9ww==`.
  Its [Sigstore/SLSA provenance](https://registry.npmjs.org/-/npm/v1/attestations/rea-agents@6.8.0)
  binds that digest to revision `160d821ac9a0310afcb8d1fc427862dd6508add5`,
  matching tag `rea-agents-6.8.0`. Verification used Sigstore 4.1.1 and
  `@sigstore/verify` 3.1.1 with refreshed TUF trust: DSSE signature, Fulcio chain,
  certificate-transparency SCT, Rekor inclusion promise/checkpoint/Merkle proof,
  GitHub OIDC issuer and exact release-workflow identity. Modified payload and
  wrong-identity negative checks were rejected. The authenticated workflow identity
  is `https://github.com/morluto/rea/.github/workflows/release.yml@refs/heads/main`,
  issuer `https://token.actions.githubusercontent.com`, event `pull_request`;
  do not describe it as a tag-triggered workflow. Preserve `dist` (including recorded
  catalog JSON), `scripts`, `bridge`, `native`, `third_party`, `licenses` and `skills`:
  runtime resources resolve relative to this layout. Official skill version **49**
  advertises **229 MCP tools**.
- **package-lock.json**: a runtime-only projection of the
  [exact release lock](https://github.com/morluto/rea/blob/160d821ac9a0310afcb8d1fc427862dd6508add5/package-lock.json).
  Delete entries marked `dev`, and remove root `devDependencies` and
  `hasInstallScript`; retain every runtime version, URL and integrity unchanged.
  `importNpmLock` fetches dependencies by upstream integrity. Lifecycle scripts
  stay disabled; compiled dist is used and the Linux PTY addon is auto-patched
  against the Nix compiler runtime. No TypeScript/Gradle build. Optional npm
  Frida 17.23.2 remains unbuilt: its downloader/native installation is not run.
  Incur's notifier is disabled; the launcher also rejects global updater flags.
- **Node 24.22.1**, scoped to REA through `node.nix`: official
  [Linux x64 archive](https://nodejs.org/dist/v24.22.1/node-v24.22.1-linux-x64.tar.xz),
  SHA-256 `6c172a9ab6718f7b801fb5a7bd486af2ee5e32758086a04b84fcce2aa77095e6`.
  The [signed checksum manifest](https://nodejs.org/dist/v24.22.1/SHASUMS256.txt.asc)
  verified with Node's release keyring at revision
  `7b6eb2d6ab524bb30487f31612cdbeb35ae37533`, already pinned by the selected
  Nixpkgs updater; keyring SHA-256 SRI
  `sha256-cNpMrJ0Eh8F3bGZAPV9v55mR8bo0+ulkFgN94ZUBl+E=`.
  Signer fingerprint: `5BE8A3F6C8A5C01D106C0AD820B1A390B168D356`.
  Repack/ELF/shebang patch only; no Node/V8 compilation or global overlay.
  Selected Nixpkgs Node 22.23.3/24.21.0/26.11.1 are cached but below REA 6.8's
  `^22.23.4 || ^24.22.1 || >=26.12.1` requirement. The chosen 24.x runtime also
  supplies SQLite's `DatabaseSync.limits`. Existing trusted caches supply the
  repack's dependencies; no cache or `flake.lock` change is needed.
- **Ghidra 12.1.4**: official
  [release ZIP](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.4_build),
  using its published SHA-256. Override the maintained Nixpkgs binary repack;
  retain matching native components, ELF patching and launch wrappers. REA 6.8.0
  still verifies this build and accepts 12.1.x with limitations. Full JDK21 is
  unchanged.
- **jadx-headless-mcp 0.7.1**: official
  [engine release](https://github.com/1013503897/jadx-headless-mcp/releases/tag/v0.7.1),
  retaining the SHA-256 in REA's
  [release identity](https://github.com/morluto/rea/blob/160d821ac9a0310afcb8d1fc427862dd6508add5/src/android/JadxRelease.ts).
  The bundled REA metadata bridge is refreshed with the CLI; the JAR stays pinned.
  This engine complements direct Nixpkgs JADX/apktool.

The upstream [release run](https://github.com/morluto/rea/actions/runs/40177214205)
reports successful published-package verification, clean-runner rehearsal, npm
publication and MCP Registry publication. These are upstream qualification results,
not certification of every local workflow. 6.6 was tagged but not published to
npm; its changes shipped in 6.7. Unreleased main is not part of this pin.

## Integrated 6.8 workflows and boundaries

All **173** non-installer primary/alias CLI routes are exposed. Upstream's count
of 175 primary commands includes maintenance and excludes our admitted alias;
compare actual name sets, not those different totals. Root persistent stdio MCP
exposes all **229** tools through native Pi/codemode; children remain CLI-only.
The official skill and references are copied unchanged with MIT attribution.
Our adapter overrides upstream installation recipes. Repeated native root work
uses one owned MCP session; slow imports stay outside 180-second runtime workers.

6.8 adds retained function summaries, resumable decompilation exports, function
matching, native exports, byte entropy, IL2CPP/Python/BEAM/model/GPU inspection,
additional PE/ELF metadata and Godot/PyInstaller/Node SEA artifact readers.
Android gains multi-locale tables and signing declarations. Supported capture
Evidence can build/export/serve/compare local environments; serving owns a listener
and exports can contain response bodies. Derived behavior is not a complete clone.

Managed absolute paths supply Apktool, owned-lab ADB, mitmdump, Chrome, GNU objdump,
TShark/capinfos and resource limiters. Wireshark 4.x is admitted; selected 4.6.9
can differ from upstream's verified build, so test saved captures locally.
No live capture permissions or system services are added.

Deferred engines remain explicit: WABT needs 1.0.42 (selected Nixpkgs has 1.0.41),
sigrok-cli needs 0.7.2 (selected Nixpkgs has 0.8.0-unstable), and the optional
Node Frida binding needs a separate native-package/runtime review. Continue using
the existing managed Frida lab. GDB/Rizin/Cutter, Kuna and optional NativeAOT
plugins are not provisioned. Licensed engines, firmware extractors, pwntools and
Wakaru remain separate prerequisites. No engine is silently downloaded or spoofed.

## Migration and policy

- Regenerate old Evidence/snapshots: 6.6–6.8 change coverage and nullable facts;
  there is no automatic saved-file migration. Browser storage comparisons need
  fresh captures on both sides. ADB version codes are decimal strings.
- MCP `analyze_function` defaults to a retained summary; request `detail: "complete"`
  for the previous inline dossier. CLI keeps complete by default; summary requires
  private `--evidence_output`. JSONL is collection rows plus a metadata record,
  not whole-document JSON. Reconstruction proof/authority projections also change.
- MCP runtime settings adjust bounded defaults for new work without restarting;
  they do not change active jobs, host/client limits or explicit call arguments.
  The launcher preserves explicit Ghidra import/decompile controls, the JADX
  operation deadline, input schema profile and reference-source exclusion patterns.
  Engine/plugin/transport configuration remains managed. Response-ceiling changes
  require a separate client buffer review.
- Published 6.8 process captures can retain sensitive terminal echoes despite input
  markers. Avoid real secrets in recordings. The echo-redaction fix, Android R8/JNI
  workflows and additional firmware readers on main are **not** shipped here.
- Discover actual schemas and retain unknowns. Catalog exposure is not engine
  availability or qualification for arbitrary artifacts.

## Maintenance and verification

Verify npm artifact/tag/signature/provenance, project the exact runtime lock,
inspect engine requirements, refresh the official skill and CLI allowlist, then
update fixtures/hashes. Leave unrelated inputs and `flake.lock` unchanged. Check
trusted caches and get approval before substantial local builds. Never accept a
mismatched hash without verifying the intended artifact.

`tests/fixtures/pi-re-rea/release-inventory.json` records release identities and
SHA-256 digests of complete sorted CLI/MCP name sets. Offline
`python3 -B tests/pi-re-rea.py` checks routes, exclusions and managed boundaries.
Build `pi-re` and `rea-fixture`, then run installed Pi loader checks and opt-in
`tests/pi-re-rea-integration.py` (native/JavaScript/SQLite/objdump and optional APK)
and `tests/pi-re-rea-workflows.py` (exact MCP inventory, runtime settings, entropy,
saved captures, PTY and optional persistent Ghidra/browser).
These use no real model/device. Optional branches are tested only when their
arguments are supplied; passing fixtures do not certify arbitrary targets or
real-device acquisition. A live agent trial is separate.
