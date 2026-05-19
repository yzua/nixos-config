# Application configuration modules.

{
  imports = [
    ./desktop-entries.nix # Desktop entries and Element keyring wrapper script
    ./keepassxc.nix # KeePassXC desktop entry
    ./obs.nix # OBS Studio with CUDA and plugins
    ./minecraft.nix # Prism Launcher and Waylandcraft Fabric instance seed
    ./syncthing.nix # Syncthing local file sync
    ./nixcord.nix # Discord (Vesktop + Vencord)
    ./activitywatch.nix # ActivityWatch app usage tracking
    ./opensnitch-ui.nix # OpenSnitch application firewall GUI
    ./nautilus.nix # Nautilus (GNOME Files) dconf preferences
    ./vscode # VS Code editor with extensions and settings
    ./brave # Brave browser with declarative extensions
    ./chromium.nix # Chromium launch wrapper with Wayland crash workaround
    ./librewolf # LibreWolf browser with declarative profile settings and policies
    ./obsidian.nix # Obsidian Markdown notes app defaults
    ./metadata-scrubber.nix # Automatic metadata scrubbing (inotifywait watcher + weekly full scrub)
    # modules-check: manual-helper ./_mk-wayland-browser-wrapper.nix
    # modules-check: manual-helper ./_desktop-local-bin-wrappers.nix
  ];
}
