# Repository guidance

## Workflow

- `flake.nix` wires one NixOS host (`PC`) and a **standalone** Home Manager profile (`yz@PC`). `README.md` documents the workflow; for Firefox profiles, GNOME input sources, MIME defaults, SOPS secrets, audio, gaming, or Tor, read the corresponding feature modules before changing behavior. Firefox profile paths do not migrate browser data.
- Start workflow changes in `justfile`. `scripts/config.sh` selects the sole NixOS/Home output or requires `NIXOS_CONFIG`/`HOME_CONFIG` when there are several. `scripts/saved-preview-build.sh` owns per-output saved builds and freshness checks. Test workflow changes with `bash tests/workflow.sh`, which mocks Nix and activation.
- `just check` warns about untracked `.nix` files and runs `just verify` (`nix flake check --no-build --no-write-lock-file .`). `just status` only evaluates active, saved, and desired generations. For read-only style checks, run `just fmt-check` and `just lint` from `nix develop`; `just fmt` writes files.
- Git flakes ignore untracked `.nix` files: stage new modules before evaluation or preview. Start each `.nix` file with a short `#` purpose header; keep the generated hardware file's warning header intact.
- `just preview` builds/diffs NixOS; `just home-preview` builds/diffs standalone Home Manager and reports managed-file conflicts and declared GNOME input sources (not arbitrary dconf changes). Successful previews save per-output links under `${XDG_STATE_HOME:-$HOME/.local/state}/nixos/`. Review the relevant preview before `just switch` or `just home-switch` (no sudo for Home Manager). Unqualified `nixos-rebuild` uses `/etc/nixos`, not this flake.
- When moving apps or settings from NixOS to Home Manager, preview and switch Home Manager **first**, then preview and switch NixOS, so apps do not disappear between activations.
- After changing NixOS or Home Manager config, run `just check` and the relevant preview when feasible. Get approval before a preview requiring a substantial local build; report validation failures rather than activating to test.

## Configuration boundaries

- Keep `flake.nix` for inputs, outputs, and tooling. Put hardware, storage, boot, hostname, account, and `system.stateVersion` in `hosts/<host>/`; leave generated hardware files intact. Import reusable NixOS features explicitly from `modules/nixos/` (small `base.nix`, opt-in feature modules).
- `home-manager/home.nix` owns the account and imports focused `home-manager/modules/`. NixOS owns system services and intentionally system-wide packages; Home Manager owns user apps/preferences. Give each setting one owner. Prefer direct option definitions and feature-named modules; add an enable option, role hierarchy, or host inventory only for real shared behavior.
- Make **all reusable content** portable: modules, workflows, app settings, templates, tests, and documentation examples. Derive identities, home/device paths, and output names from the selected configuration or caller; if selection is ambiguous, ask for `NIXOS_CONFIG`/`HOME_CONFIG` rather than guess. Concrete identities belong only in the dedicated host/profile and flake wiring; migration history in docs may name this machine, but reusable examples should not.

## Safety constraints

- Before adding/installing a package, check whether configured trusted caches provide it. For substantial local builds, prefer a maintained prebuilt Nixpkgs variant or official binary packaged through Nix when suitable; explain the tradeoff and get approval before building. Add no untrusted caches or unverified binaries silently.
- Preserve the installed `system.stateVersion` and `home.stateVersion`; change only for a deliberate, reviewed state migration, not a routine dependency update.
- Keep credentials, tokens, passwords, and private keys out of Git and plaintext secrets out of Nix store paths. Discuss secret management before introducing a new approach.
- Keep dependency edits focused: update `flake.lock` and unrelated inputs only in a separately reviewed dependency change with build previews. If a fixed-output hash mismatches, verify the intended upstream artifact before accepting a new hash.
- Preserve activation guards: NixOS hostname must match the running host unless a rename is explicitly approved; Home Manager user/home must match the caller. Switch only the saved, still-current preview build; `check` and `status` must never activate.
