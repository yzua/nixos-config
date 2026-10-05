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
Successful previews retain their builds with per-output GC roots under the caller's
XDG state directory. Failed builds or reviews leave the previous saved preview intact.
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
Run `just test` for the explicit offline regression suites, including generation
workflows, voice actions, Pi extensions/subagents, and the RE profile/lab mocks.
These tests use isolated fixtures without activation or paid model calls. Generated-config tests require managed Niri and tmux. The
loader tests require managed Pi, Bun, and installed web-fetch dependencies;
`PI_BIN` and `PI_WEB_FETCH_DIR` can select alternate installations. Live desktop
focus, browser, and Android lab checks remain separate opt-in commands.
`just test-preview-roots-gc` separately verifies preview retention by running GC
only in a disposable local Nix store, never on the workstation store.

## Bluetooth and AirPods

Bluetooth adapters use BlueZ with Blueman for pairing and PipeWire/WirePlumber
for audio and media buttons. Firmware remains part of the host's normal hardware
support; no adapter address is hardcoded.

LibrePods uses the pinned upstream Rust client in `packages/librepods-rust/`, not
Nixpkgs's legacy Qt client. NixOS owns its application and restricted
`CAP_NET_ADMIN` wrapper; the configured account belongs to the `librepods` group.
Home Manager owns its desktop launcher and minimized graphical-session startup.
GNOME uses AppIndicator support for the tray; Noctalia provides the tray in Niri.
The pinned source is packaged without local application patches. Its tray uses
a battery ring or percentage text, not the app logo. The sidebar may display a
disconnected case as `0%`; consult the tooltip, where `C: -` means unavailable.
Upstream logs can include device identifiers and proximity keys; do not share
raw logs without redacting them.

Preview both outputs before activation. Apply the NixOS preview with `just switch`
and the Home Manager preview with `just home-switch`. A new supplementary group
requires a fresh login/user-manager session; merely opening a new terminal or
restarting a user service may retain the old groups. For a one-off test without
logging out, after activation run:

```sh
sg librepods -c '/run/wrappers/bin/librepods'
```

Do not run LibrePods as root or manually apply capabilities to a writable binary.
The capability permits low-level network administration, so only grant group
membership to accounts intended to use it. User settings and pairing credentials
stay outside Git and the Nix store.

For AirPods Pro 3, open the case with the earbuds inside and double-tap its front
until the light flashes white, then pair/trust/connect through Blueman. Launch
LibrePods after pairing. Use the tray's **Open Window** menu, then select the
AirPods under **Devices**. Check battery reporting, listening-mode changes,
ear detection, and playback controls. For a case battery update, put at least
one earbud in the case and wait a few seconds; case-only reporting with both
buds out is not implemented. Features depend on firmware and upstream
implementation; the Rust rewrite is still development software. Apple-identity
spoofing and experimental disconnected-device monitoring are not enabled.

Ordinary Bluetooth headset microphone use can reduce playback quality compared
with the A2DP music profile. This setup does not promise Apple's high-quality
two-way audio, spatial audio, Find My, or heart-rate monitoring. Keep a separate
microphone when high-quality music playback matters.

## Customize

Edit `setup` in `flake.nix` for the host, user, locale, keyboard, display,
graphics, and Git settings. Output names follow the configured host and user.
`setup.monitors` declares each display's match string (from `niri msg outputs`),
mode, scale, transform, logical position, and primary status. Keep one display
`primary = true` to focus it at startup and place named startup workspaces there.
Set `monitors = [ ];` for automatic output placement and preferred display modes.
Transforms `"90"` and `"270"` rotate counter-clockwise; positions use the scaled,
rotated desktop dimensions, not the unrotated display mode.

### Niri monitor controls

`Super` is the Windows key. The configured displays form one extended desktop;
move the pointer across their shared edge to switch screens.

| Shortcut | Action |
| --- | --- |
| Super + Alt + Arrow | Focus the monitor in that direction |
| Super + Shift + Arrow | Move the focused window to that monitor |
| Super + Ctrl + Shift + Arrow | Move the whole column to that monitor |
| Super + Ctrl + Arrow | Rearrange windows/columns within the current monitor |
| Super + 1–4 | Focus the named startup workspace, including across monitors |

H/J/K/L also work for window movement and local rearrangement. Workspace 1–4
shortcuts target names rather than monitor-local indices; 5–9 target indices on
the focused monitor. Startup placement is not a lock: windows and workspaces can
still be moved afterward. Noctalia shows a bar on each connected monitor, with
that monitor's windows in its taskbar. Shortcut-opened panels (launcher,
clipboard, control center) follow the focused monitor.

For another machine, regenerate the host's `hardware-configuration.nix` and
review its boot settings. Keep the installed `stateVersion` values when
updating dependencies. Use your own Git signing and SOPS age keys outside the
Nix store, and re-encrypt the SOPS secrets for your key.

VS Code settings are a writable Nix-defined baseline: activation backs up and
resets differing settings, while subsequent editor writes remain possible.
Persistent preference changes belong in `home-manager/modules/vscode/settings.nix`.

## Layout

- `flake.nix` and `flake.lock`: outputs and pinned dependencies.
- `hosts/`: hardware and host settings. `modules/nixos/` holds reusable system
  settings, grouped into `desktop/` infrastructure and `networking/` VPN/Tor
  services, with explicit imports in each host.
- `packages/`: custom package definitions and their sources, shared by flake
  outputs and profiles.
- `home-manager/`: user apps and preferences. Under `modules/`, `desktop/`
  groups GNOME, Niri, and Noctalia settings; `desktop-apps/` owns applications;
  `terminal/` groups CLI tools, terminal/shell settings, tmux, and Git.
- `justfile`: command menu and checks; `scripts/generation.sh`: previews, status,
  and guarded switches.

## License

Licensed under the [WTFPL, version 2](LICENSE).
