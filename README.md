# NixOS + Home Manager

Personal NixOS flake for `PC` and standalone Home Manager profile `yz@PC`.
NixOS owns the machine; Home Manager owns user apps and preferences.

## Quick start

From the repo root, with Nix flakes and `just` available (or enter the
project's tool shell with `nix develop`):

```sh
just check          # headers, flake evaluation, and duplicate package declarations
just status         # active vs. saved preview vs. desired generations
```

Neither command builds or activates. `just check` warns about untracked `.nix`
files, checks purpose headers, runs `nix flake check --no-build` and detects
duplicates in package lists declared by this repo (not packages supplied by
NixOS/Home Manager modules). Stage new `.nix` files before evaluation: Git
flakes do not see untracked files.

## Preview and activation

```sh
just home-preview   # build and compare the Home Manager activation
just preview        # build and compare the NixOS system closure
```

Previews may download or build packages, but do not activate anything. The Home
preview also lists managed files, existing-path conflicts, no-longer-managed
files, and declared GNOME input sources; it is **not** a complete dconf diff.
Review the relevant preview, then explicitly run `just home-switch` (as the
user, without sudo) or `just switch` for NixOS. Switches use the saved preview
build only if it still matches the selected output. The NixOS switch checks the
hostname; the Home Manager switch checks the user and home directory.

If moving apps or settings from NixOS to Home Manager, preview and switch
**Home Manager first**, then preview and switch NixOS, so apps remain available.
Each selected output keeps its own saved preview under
`${XDG_STATE_HOME:-$HOME/.local/state}/nixos/`. Set `NIXOS_CONFIG` or
`HOME_CONFIG` for a different output or if automatic selection is ambiguous.
Older shared `result-system`/`result-home` links are ignored: preview again
before switching after adopting this workflow. Unqualified `nixos-rebuild`
uses `/etc/nixos`, not this flake.

## Development checks

In the project dev shell (`nix develop`), run `just fmt-check` and `just lint`
for read-only formatting and static analysis. `just fmt` edits Nix, shell, and
the justfile; the generated hardware file is excluded from formatting. For
changes to preview/switch scripts, run `bash tests/workflow.sh` too: it mocks
Nix and activation, so it needs neither a real build nor a switch. The workflow
tests are not part of `just check`. Use `just --list` for other recipes.

## Layout

- `flake.nix` and `flake.lock`: outputs and pinned dependencies.
- `hosts/PC/` and `modules/nixos/`: machine settings and system features.
- `home-manager/home.nix` and `home-manager/modules/`: user apps and preferences.
- `justfile` and `scripts/`: checks, previews, and guarded switches.

## License

Licensed under the [WTFPL, version 2](LICENSE).
