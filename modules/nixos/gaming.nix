# Steam with SLSsteam, optional Proton runners, GameMode, and per-game MangoHud.

{ pkgs, ... }:

let
  slssteam = pkgs.callPackage ../../packages/slssteam { };
in
{
  programs.steam.enable = true;
  # Use upstream's NixOS integration, not Headcrab's client downgrade/patcher.
  programs.steam.package = pkgs.steam.override {
    extraEnv.LD_AUDIT = "${slssteam}/library-inject.so:${slssteam}/SLSsteam.so";
  };
  programs.steam.extraPackages = [ pkgs.mangohud ];
  # Register alternatives without changing Steam's default or per-game choice.
  programs.steam.extraCompatPackages = [
    pkgs.proton-ge-bin
    (pkgs.callPackage ../../packages/proton-cachyos-bin { })
  ];
  programs.gamemode.enable = true;
}
