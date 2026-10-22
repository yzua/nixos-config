# User-level gaming apps, overlays, and opt-in Proton fullscreen mouse capture.

{ lib, pkgs, ... }:

let
  slssteam = pkgs.callPackage ../../packages/slssteam { };
  accelaConfig = pkgs.writeText "accela-initial.conf" ''
    [General]
    auto_skip_single_choice=true
    library_mode=true
    max_downloads=16
    sls_config_management=true
    slssteam_mode=true
    use_steamless=true
  '';
  steamMouseGrab = pkgs.writeShellScriptBin "steam-mouse-grab" ''
    exec ${lib.getExe pkgs.python3} ${./steam-mouse-grab.py} "$@"
  '';
in
{
  programs.mangohud.enable = true;

  # ACCELA updates game-specific entries, so seed a writable config rather than
  # linking it into the read-only store. Never replace an existing user config.
  home.activation.seedGamingConfigs = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    config_dir="''${XDG_CONFIG_HOME:-$HOME/.config}/SLSsteam"
    if [[ ! -e "$config_dir/config.yaml" && ! -L "$config_dir/config.yaml" ]]; then
      run mkdir -p "$config_dir"
      run install -m 600 ${slssteam}/share/SLSsteam/config.yaml "$config_dir/config.yaml"
    fi
    accela_config="''${XDG_CONFIG_HOME:-$HOME/.config}/Tachibana Labs/ACCELA.conf"
    if [[ ! -e "$accela_config" && ! -L "$accela_config" ]]; then
      run mkdir -p "$(dirname "$accela_config")"
      run install -m 600 ${accelaConfig} "$accela_config"
    fi
  '';

  xdg.mimeApps.defaultApplications."x-scheme-handler/accela" = [ "accela.desktop" ];
  xdg.mimeApps.associations.added."x-scheme-handler/accela" = [ "accela.desktop" ];

  home.packages = [
    (pkgs.callPackage ../../packages/accela { })
    steamMouseGrab
    (pkgs.lutris.override {
      steamSupport = false;
      extraPkgs = p: [ p.mangohud ];
    })
  ];
}
