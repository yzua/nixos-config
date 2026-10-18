# Standalone MacBook home: coding, on-demand RE lab, voice, and desktop essentials.

{
  lib,
  pkgs,
  setup,
  ...
}:

{
  imports = [
    ./modules/ai/cli.nix
    ./modules/ai/pi-re
    ./modules/ai/voice
    ./modules/desktop
    ./modules/desktop-apps/firefox.nix
    ./modules/desktop-apps/keepassxc.nix
    ./modules/desktop-apps/netbird.nix
    ./modules/desktop-apps/pc-desktop.nix
    ./modules/desktop-apps/vesktop.nix
    ./modules/mime.nix
    ./modules/terminal
    ./modules/theme.nix
    ./modules/vscode
  ];

  home.username = setup.username;
  home.homeDirectory = setup.homeDirectory;
  home.stateVersion = setup.stateVersion.home;
  programs.home-manager.enable = true;

  home.packages = [
    pkgs.google-chrome
    pkgs.localsend
    pkgs.qbittorrent
    pkgs.telegram-desktop
  ];

  # No gaming overlay or first-activation test secret on the laptop.
  stylix.targets.mangohud.enable = lib.mkForce false;
}
