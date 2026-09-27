# NixOS + Home Manager

Personal NixOS flake for `PC` and standalone Home Manager profile `yz@PC`.
NixOS owns the machine; Home Manager owns user apps and preferences.

## Quick start

From the repo root, with Nix flakes and `just` available (or enter the
project's tool shell with `nix develop`):

```sh
just check          # warn about untracked Nix files and evaluate the flake
just status         # active vs. saved preview vs. desired generations
```

Neither command builds or activates. Stage new `.nix` files before evaluation:
Git flakes do not see untracked files.

## Preview and activation

```sh
just home-preview   # build and compare the Home Manager activation
just preview        # build and compare the NixOS system closure
```

Previews may download or build packages, but do not activate anything. A
successful preview saves the build that its switch command will use. The Home
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

Home preview and status refuse an output belonging to another user or home
directory rather than compare it with the caller's active state. The sole NixOS
or Home output is selected automatically; when a flake has several, set
`NIXOS_CONFIG` or `HOME_CONFIG` explicitly.

## Development checks

In the project dev shell (`nix develop`), run `just fmt-check` and `just lint`
for read-only formatting and static analysis. `just fmt` edits Nix, shell, and
the justfile; the generated hardware file is excluded from formatting. For
changes to preview/switch scripts, run `bash tests/workflow.sh` too: it mocks
Nix and activation, so it needs neither a real build nor a switch. The workflow
tests are not part of `just check`. Use `just --list` for other recipes.

## Appearance

The standalone Home Manager profile uses Stylix's `release-26.05` module for
Gruvbox Dark Soft, IBM Plex Sans with its matching Arabic face for desktop text,
Noto Serif and Amiri for documents, JetBrains Mono for terminals, and Noto Color
Emoji. Noto CJK and Nerd Symbols fill other script and terminal icon gaps.
Edit `home-manager/modules/theme.nix` to change the palette or fonts, then run
`just check` and `just home-preview`
before `just home-switch`. The user GNOME shell, GTK apps, Firefox's Personal
and Work profiles, Ghostty, and the configured terminal tools receive the
palette. VS Code keeps its existing Gruvbox Dark Soft extension and writable
settings. GDM is not themed by this user-level module.

## Desktop sessions

GDM offers both GNOME and Niri. GNOME remains available while Niri is tested.
The Niri system module installs the session and Xwayland Satellite for X11
games. Home Manager owns Niri's keyboard and shortcuts and starts Noctalia
only in the Niri session.

In Niri, `Mod` is the Super key. Caps Lock switches between US and Arabic
(Shift+Caps Lock retains the normal Caps Lock action). `Mod+Enter` opens
Ghostty, `Mod+Space` opens the app launcher, `Mod+S` opens the control center,
`Mod+V` opens clipboard history, `Mod+Shift+Comma` opens Noctalia settings,
and `Mod+Home` locks. `Mod+F` toggles floating, `Mod+M` maximizes the window
while keeping the bar visible, and `Mod+Shift+F` toggles fullscreen.
`Mod+Shift+Arrow` moves the focused window or column, `Mod+Shift+1` through
`Mod+Shift+9` move the focused window to a workspace, and `Mod+Alt+Arrow`
focuses another monitor.
`Mod+Shift+Slash` shows Niri's shortcut overlay. GNOME keeps its own input
shortcuts. Noctalia's bar shows each window icon in its workspace taskbar group.
GNOME Tweaks is available in the GNOME session.

The Phinger pointer theme is shared by Niri and GNOME. Niri asks apps to hide
window title bars when they support it; apps with built-in header bars may keep
them. Ghostty hides its title and tab bars. Use `Ctrl+Shift+T` for a new Ghostty
tab, `Ctrl+Tab` to move forward, and `Ctrl+Shift+Tab` to move backward.

Edit `home-manager/modules/niri.nix` for compositor settings and
`home-manager/modules/noctalia.nix` for stable shell settings. Noctalia's GUI
writes overrides to `${XDG_STATE_HOME:-$HOME/.local/state}/noctalia/settings.toml`;
those values take precedence over the Nix-managed TOML until cleared. Use
`noctalia config export` to review choices before moving them into the module.
Stylix continues to theme applications; Noctalia's application templates are
disabled.

## Layout

- `flake.nix` and `flake.lock`: outputs and pinned dependencies.
- `hosts/PC/` and `modules/nixos/`: machine settings and system features.
- `home-manager/home.nix` and `home-manager/modules/`: user apps and preferences.
- `justfile` and `scripts/`: checks, previews, and guarded switches.

## License

Licensed under the [WTFPL, version 2](LICENSE).
