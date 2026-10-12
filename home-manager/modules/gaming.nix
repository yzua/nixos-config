# User-level gaming apps, overlays, and opt-in Proton fullscreen mouse capture.

{ lib, pkgs, ... }:

let
  steamMouseGrab = pkgs.writeShellScriptBin "steam-mouse-grab" ''
    exec ${lib.getExe pkgs.python3} ${./steam-mouse-grab.py} "$@"
  '';
in
{
  programs.mangohud.enable = true;

  home.packages = [
    steamMouseGrab
    (pkgs.lutris.override {
      steamSupport = false;
      extraPkgs = p: [ p.mangohud ];
    })
  ];
}
