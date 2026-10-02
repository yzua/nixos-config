# Standalone Home Manager entry point for this account and its user modules.

{ setup, ... }:

{
  imports = [
    ./modules/ai
    ./modules/desktop
    ./modules/desktop-apps
    ./modules/gaming.nix
    ./modules/mime.nix
    ./modules/secrets.nix
    ./modules/terminal
    ./modules/theme.nix
    ./modules/vscode
  ];

  home.username = setup.username;
  home.homeDirectory = setup.homeDirectory;
  home.stateVersion = setup.stateVersion.home;

  programs.home-manager.enable = true;
}
