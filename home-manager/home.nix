# Standalone Home Manager entry point for this account and its user modules.

{ homeProfile, ... }:

{
  imports = [
    ./modules/ai.nix
    ./modules/cli.nix
    ./modules/desktop-apps.nix
    ./modules/firefox.nix
    ./modules/gaming.nix
    ./modules/ghostty.nix
    (import ./modules/git.nix { inherit (homeProfile) gitIdentity; })
    ./modules/gnome.nix
    ./modules/keepassxc.nix
    ./modules/mime.nix
    ./modules/secrets.nix
    ./modules/shell.nix
    ./modules/skills.nix
    ./modules/vesktop.nix
    ./modules/vscode
  ];

  home.username = homeProfile.username;
  home.homeDirectory = homeProfile.homeDirectory;
  home.stateVersion = "26.05";

  programs.home-manager.enable = true;
}
