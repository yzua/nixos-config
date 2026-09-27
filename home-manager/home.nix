# Standalone Home Manager entry point for this account and its user modules.

{ homeProfile, ... }:

{
  imports = [
    ./modules/ai
    ./modules/desktop-apps
    ./modules/gaming.nix
    (import ./modules/git.nix { inherit (homeProfile) gitIdentity; })
    ./modules/gnome.nix
    ./modules/mime.nix
    ./modules/niri.nix
    ./modules/noctalia.nix
    ./modules/secrets.nix
    ./modules/terminal
    ./modules/theme.nix
    ./modules/vscode
  ];

  home.username = homeProfile.username;
  home.homeDirectory = homeProfile.homeDirectory;
  home.stateVersion = "26.05";

  programs.home-manager.enable = true;
}
