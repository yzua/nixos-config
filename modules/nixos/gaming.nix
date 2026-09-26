# Opt-in Steam, GameMode, and per-game MangoHud support for gaming hosts.

{ pkgs, ... }:

{
  programs.steam.enable = true;
  programs.steam.extraPackages = [ pkgs.mangohud ];
  programs.gamemode.enable = true;
}
