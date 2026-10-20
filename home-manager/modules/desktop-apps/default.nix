# Install graphical desktop apps and import their app-specific settings.

{ pkgs, ... }:

{
  imports = [
    ./easyeffects.nix
    ./firefox.nix
    ./keepassxc.nix
    ./netbird.nix
    ./peripherals.nix
    ./vesktop.nix
    ./yubikey.nix
  ];

  # These apps need no extra extensions.
  home.packages = [
    pkgs.google-chrome
    pkgs.localsend
    pkgs.obs-studio
    pkgs.qbittorrent
    pkgs.sqlitebrowser
    pkgs.telegram-desktop
  ];
}
