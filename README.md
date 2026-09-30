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

## Customize

Edit `setup` in `flake.nix` for the host, user, locale, keyboard, display,
graphics, and Git settings. Output names follow the configured host and user.
Set `monitor = null` to use the display's preferred mode.

For another machine, regenerate the host's `hardware-configuration.nix` and
review its boot settings. Keep the installed `stateVersion` values when
updating dependencies. Use your own Git signing and SOPS age keys outside the
Nix store, and re-encrypt the SOPS secrets for your key.

## Layout

- `flake.nix` and `flake.lock`: outputs and pinned dependencies.
- `hosts/` and `modules/nixos/`: hardware and system settings.
- `home-manager/`: user apps and preferences.
- `justfile` and `scripts/`: checks, previews, and guarded switches.

## License

Licensed under the [WTFPL, version 2](LICENSE).
