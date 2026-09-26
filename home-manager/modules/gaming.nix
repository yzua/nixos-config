# User-level Lutris and opt-in MangoHud without a second Steam runtime.

{ pkgs, ... }:

{
  programs.mangohud.enable = true;

  home.packages = [
    (pkgs.lutris.override {
      steamSupport = false;
      extraPkgs = p: [ p.mangohud ];
    })
  ];
}
