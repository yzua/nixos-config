# REA package provenance

This package set supplies `pi-re`'s CLI/root MCP and matching official skill on
Linux x86_64. It installs no upstream client registrations or skills into ordinary
coding Pi. Only the isolated RE profile loads the bundled upstream skill.

## Pinned artifacts

- **rea-agents 6.4.0**: the compiled official
  [npm artifact](https://registry.npmjs.org/rea-agents/6.4.0), verified against
  registry SHA-512 integrity and matching tag/npm gitHead
  `a56f7bb668ab23fec8d33f7af353ac7ed2fe1895`. The package ships compiled code but
  no node_modules/lockfile. Preserve `dist`, `scripts`, `bridge`, `native`,
  `third_party`, `licenses` and `skills` layout: runtime code resolves resources
  relative to it. Its official skill is version 37 with 170 advertised MCP tools.
- **package-lock.json**: a runtime-only projection of the
  [release lock](https://github.com/morluto/rea/blob/a56f7bb668ab23fec8d33f7af353ac7ed2fe1895/package-lock.json).
  Delete package entries marked `dev`, and remove root `devDependencies` and
  `hasInstallScript`; retain every runtime version, URL and integrity unchanged.
  `importNpmLock` fetches each dependency by its upstream integrity. Lifecycle
  scripts are disabled, compiled dist is used, and the Linux PTY addon is
  auto-patched against the Nix compiler runtime. No TypeScript/Gradle build.
  Incur's automatic update notifier is disabled; the `pi-re` route also rejects
  global updater flags before dispatch.
- **Ghidra 12.1.4**: official
  [release ZIP](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.4_build),
  using its published raw SHA-256 digest. Override the maintained Nixpkgs binary
  repack; keep matching native decompiler components, ELF patching and launch
  wrappers. REA 6.4.0 verifies 12.1.4 and accepts 12.1.x; retain the verified
  build and full JDK21 rather than substituting/spoofing the stock 12.0.x package.
- **jadx-headless-mcp 0.7.1**: official
  [engine release](https://github.com/1013503897/jadx-headless-mcp/releases/tag/v0.7.1),
  pinned to the SHA-256 audited in REA's
  [release identity](https://github.com/morluto/rea/blob/a56f7bb668ab23fec8d33f7af353ac7ed2fe1895/src/android/JadxRelease.ts).
  This additional query engine complements the direct Nixpkgs JADX/apktool pack.

## Maintenance

Treat an update as a focused dependency change: verify the npm release/tag,
regenerate only its runtime lock projection, inspect engine/JDK requirements and
published artifact digests, then update fixed hashes. Leave `flake.lock` and
unrelated inputs unchanged. Check trusted cache availability and get approval
before substantial local builds. Do not accept a mismatched hash without verifying
the intended upstream artifact.

Run offline `tests/pi-re-rea.py`, installed loader checks, and the opt-in
`tests/pi-re-rea-integration.py` against the built `pi-re` and `rea-fixture` outputs.
The integration test covers owned native/JavaScript inputs and, when supplied,
the existing owned Android fixture. It does not certify every binary or workflow.
A live agent trial is separate from deterministic backend and loader tests.

The root now connects its own persistent stdio MCP server through Pi's native
MCP/codemode support, exposing all advertised tools without injecting all schemas
into every request. Its official skill and six references are copied unchanged
from this exact npm package into immutable profile resources, with MIT attribution.
The local `rea-analysis` adapter/contract override upstream installation recipes.
Children remain CLI-only; snapshots do not constitute a persistent database.

All 125 non-installer primary/alias CLI routes are enabled. Managed absolute paths
wire existing Apktool, ADB, mitmdump 12.2.3, Chrome and resource limiters; ADB uses
the owned rooted-lab transport, not arbitrary attached devices. Optional licensed,
firmware, pwntools and Wakaru engines are not silently acquired. Read the runtime
command guide for prerequisites and platform boundaries.
