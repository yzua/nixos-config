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

Each selected NixOS or Home Manager output keeps its own saved preview build.
Set `NIXOS_CONFIG` or `HOME_CONFIG` to select an output when needed. Older shared
`result-system` and `result-home` links are ignored; run the corresponding
preview again before switching after adopting this workflow.

Stage new `.nix` files before checking: Git flakes cannot see untracked files.
Run `just --list` for other commands.

## Layout

- `flake.nix` and `flake.lock`: outputs and pinned dependencies.
- `hosts/PC/` and `modules/nixos/`: machine settings and system features.
- `home-manager/home.nix` and `home-manager/modules/`: user apps and preferences.
- `justfile` and `scripts/`: checks, previews, and guarded switches.

## Audio

`modules/nixos/audio.nix` keeps PipeWire separate from GNOME and adds RNNoise
microphone suppression. WirePlumber inserts the filter for recordings from the
default input; select the physical mic in GNOME Sound rather than choosing a
separate virtual device. It is available each session but only processes audio
while the mic is in use. Apps recording outside PipeWire, or targeting a
different non-default mic, may bypass it.

After reviewing `just preview` and explicitly running `just switch`, log out
and back in (or restart the user PipeWire service, which interrupts audio) to
load the filter. Check `wpctl status` and make a test recording. If speech is
cut off, lower `VAD Threshold (%)` in the audio module; avoid stacking another
noise-suppression effect in the calling app.

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

## Tor

`modules/nixos/tor.nix` enables a Tor client on the local SOCKS port (9050) and
the `torsocks` command. Only applications explicitly using that proxy go through
Tor; this does not change system DNS, transparently route traffic, or guarantee
that other applications use Tor. The same module marks the Tor service
account's outbound traffic for Mullvad's split-tunnel routing; it goes through
the regular network even when Mullvad is connected. This also means the local
network/ISP can see that Tor is connecting to entry relays,
and it can still connect while Mullvad blocks other traffic. DNS handled by
other processes is not part of this exclusion. Check the routing on a live
system after switching, especially after updating Mullvad. For anonymous web
browsing, use Tor Browser rather than pointing a regular browser at this proxy.

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
