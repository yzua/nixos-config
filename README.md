# NixOS + Home Manager

Personal NixOS flake for `PC` and standalone Home Manager profile `yz@PC`.
NixOS owns the machine; Home Manager owns user apps and preferences.

## Use

From this directory, with Nix flakes and `just` available:

```sh
just check          # evaluate both configs; no build or activation
just status         # show active, saved, and desired generations
just home-preview   # build and review Home Manager changes
just preview        # build and review NixOS changes
```

`check` and `status` do not build or activate anything. Previews build but do
not activate; review them before running `just home-switch` (without sudo) or
`just switch`. If moving apps to Home Manager, preview and switch **Home Manager
first**, then preview and switch NixOS. Previews may download or build packages.

Stage new `.nix` files before checking: Git flakes cannot see untracked files.
Run `just --list` for other commands.

## Layout

- `flake.nix` and `flake.lock`: outputs and pinned dependencies.
- `hosts/PC/` and `modules/nixos/`: machine settings and system features.
- `home-manager/home.nix` and `home-manager/modules/`: user apps and preferences.
- `justfile` and `scripts/`: checks, previews, and guarded switches.

## Games

The opt-in `modules/nixos/gaming.nix` enables Steam and GameMode. Home Manager
installs Lutris without a second Steam inside its runtime. MangoHud is available
in both Steam and Lutris, but is not enabled for every game. In Steam Launch
Options, use `mangohud %command%` for the performance overlay,
`gamemoderun %command%` for GameMode, or `mangohud gamemoderun %command%` for
both. In Lutris, enable advanced System options and set the game's Command
prefix to `mangohud`. Configure game runners and accounts in Lutris; Steam
manages its own Proton versions and game downloads. Gamescope, GE-Proton,
system-wide Wine, and Steam LAN firewall ports are not enabled by default.

## User settings

- **Firefox** (`home-manager/modules/firefox.nix`): changing a profile path
  can create an empty profile; browser data is not moved automatically.
- **GNOME input sources** (`home-manager/modules/gnome.nix`): these are dconf
  settings, not part of the closure diff. `just home-preview` shows them separately.
- **MIME defaults** (`home-manager/modules/mime.nix`): check managed-file
  conflicts in `just home-preview` before replacing local settings.
- **User secrets** (`home-manager/modules/secrets.nix`): only encrypted files
  belong in `secrets/`. Keep private keys and plaintext credentials outside Git
  and the Nix store.

## License

Licensed under the [WTFPL, version 2](LICENSE).
