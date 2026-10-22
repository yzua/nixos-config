# Opt-in Steam, GameMode, and per-game MangoHud support for gaming hosts.

{ pkgs, ... }:

{
  programs.steam.enable = true;
  programs.steam.extraPackages = [ pkgs.mangohud ];
  # Register alternatives without changing Steam's default or per-game choice.
  programs.steam.extraCompatPackages = [
    pkgs.proton-ge-bin
    (pkgs.callPackage ../../packages/proton-cachyos-bin { })
  ];
  programs.gamemode.enable = true;
}
