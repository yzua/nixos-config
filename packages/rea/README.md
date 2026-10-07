# REA package provenance

This package set is for `pi-re`'s static CLI on Linux x86_64. It installs no
upstream client registrations or skills into ordinary coding Pi.

## Pinned artifacts

- **rea-agents 4.1.0**: the compiled official
  [npm artifact](https://registry.npmjs.org/rea-agents/4.1.0), verified against
  registry SHA-512 integrity. The published package contains no dependencies or
  lockfile; its relative `dist`, `scripts`, `bridge` and skill layout is retained.
- **package-lock.json**: a runtime-only projection of the
  [release lock](https://github.com/morluto/rea/blob/9622b4b4cf0b2eb92305afd52fd67e932d57c753/package-lock.json).
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
  wrappers. REA 4.1.0's actual probe requires this exact version and full JDK21,
  so the stock pinned Nixpkgs version is not substituted or spoofed.
- **jadx-headless-mcp 0.7.1**: official
  [engine release](https://github.com/1013503897/jadx-headless-mcp/releases/tag/v0.7.1),
  pinned to the SHA-256 audited in REA's
  [release identity](https://github.com/morluto/rea/blob/9622b4b4cf0b2eb92305afd52fd67e932d57c753/src/android/JadxRelease.ts).
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

CLI integration deliberately avoids a persistent MCP server. Native CLI calls can
repeat import work; snapshots are evidence caches with operation-specific limits,
not a general persistent Ghidra database. Runtime operations continue through
`pi-re`'s owned lab and reviewed skills.
