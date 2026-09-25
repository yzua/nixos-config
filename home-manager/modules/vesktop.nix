# Manage Vesktop through Nixcord without rebuilding the cached Nixpkgs package.

{ nixcord, ... }:

{
  imports = [ nixcord.homeModules.nixcord ];

  programs.nixcord = {
    enable = true;
    discord.enable = false;
    vesktop = {
      enable = true;
      # Nixcord otherwise switches on a package override that builds Vesktop locally.
      useSystemVencord = false;
    };
  };
}
