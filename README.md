# NixOS + Home Manager

Workstation configuration with standalone Home Manager. NixOS manages the
system; Home Manager manages user apps and preferences.

## Usage

Run commands from the repo root. Use `nix develop` if the tools are missing.

```sh
just check          # validate the configuration
just status         # show active, previewed, and desired generations
```

These commands do not build or activate anything. Stage new `.nix` files
before checking, because Git flakes ignore untracked files.

For user apps and settings:

```sh
just home-preview   # build and review changes
just home-switch    # apply the reviewed build, without sudo
```

For system settings:

```sh
just preview        # build and review changes
just switch         # apply the reviewed build
```

Review each preview before switching. Switches require a current saved preview
and check the system hostname or Home Manager user and home directory.
When moving apps from NixOS to Home Manager, apply Home Manager first.
With multiple outputs, select one using `NIXOS_CONFIG` or `HOME_CONFIG`.

Development tools come from the pinned Nixpkgs input; no npm or pip install is
needed. In `nix develop`, run `just fmt` to format files, `just fmt-check` for a
read-only formatting check, and `just lint` for static analysis. Biome handles
the locally owned TypeScript sources; Ruff handles Python formatting, import
ordering, and common mistakes. Package lockfiles stay outside the formatter.
Biome keeps its recommended rules with a few style and extension-interop
exceptions; missing callback returns and unused code still get checked.
ShellCheck checks Bash; shfmt formats it. Rust-based rumdl checks and formats
Markdown, including links and structures that affect rendering, without
requiring line wrapping or headings in prompt fragments. For quick focused
checks, use `just lint-ts`, `just lint-python`, `just lint-shell`, or
`just lint-markdown`.
For regression checks, run `bash tests/workflow.sh`, `python3 tests/voice-action.py`,
`python3 tests/pi-config.py`, `python3 tests/pi-subagents.py`, and
`python3 tests/pi-extensions.py`. They use isolated
fixtures without activation or paid model calls.

## Customize

Edit `setup` in `flake.nix` for the host, user, locale, keyboard, display,
graphics, and Git settings. Output names follow the configured host and user.
Set `monitor = null` to use the display's preferred mode.

Pi's reviewed extensions and agent profiles live in
[`home-manager/modules/ai/pi`](home-manager/modules/ai/pi/README.md). Its live
settings and credentials remain writable; `/thinking` changes reasoning effort.
The separate [`pi-re` foundation](home-manager/modules/ai/pi-re/README.md) provides
an independent host-mode RE profile and owned rooted Android emulator. Run
`nix run .#pi-re -- doctor --json` without activation; configure the initial lab
through `setup.androidLab`. Broader capability/workflow qualification is pending.

Voice actions share conversation context until reset. Reset discards a recording
or transcription that has not been submitted; an executing request finishes in
its original context.

For another machine, regenerate the host's `hardware-configuration.nix` and
review its boot settings. Keep the installed `stateVersion` values when
updating dependencies. Use your own Git signing and SOPS age keys outside the
Nix store, and re-encrypt the SOPS secrets for your key.

## Layout

- `flake.nix` and `flake.lock`: outputs and pinned dependencies.
- `hosts/`: hardware and host settings. `modules/nixos/` holds reusable system
  settings, grouped into `desktop/` infrastructure and `networking/` VPN/Tor
  services, with explicit imports in each host.
- `packages/`: custom package definitions shared by flake outputs and profiles.
- `home-manager/`: user apps and preferences. Under `modules/`, `desktop/`
  groups GNOME, Niri, and Noctalia settings; `desktop-apps/` owns applications;
  `terminal/` groups CLI tools, terminal/shell settings, and Git.
- `justfile`: command menu and checks; `scripts/generation.sh`: previews, status,
  and guarded switches.

## License

Licensed under the [WTFPL, version 2](LICENSE).
