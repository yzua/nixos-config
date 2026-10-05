# Install graphical desktop apps and import their app-specific settings.

{ pkgs, ... }:

{
  imports = [
    ./firefox.nix
    ./keepassxc.nix
    ./librepods.nix
    ./netbird.nix
    ./vesktop.nix
  ];

  # These apps need no extra extensions.
  home.packages = [
    pkgs.google-chrome
    pkgs.obs-studio
    pkgs.sqlitebrowser
    pkgs.telegram-desktop
  ];
}
