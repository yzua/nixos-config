# System report option definitions.

{ lib, optionHelpers, ... }:

let
  inherit (optionHelpers)
    mkStrOption
    mkIntOption
    ;
in
{
  options.mySystem.systemReport = {
    enable = lib.mkEnableOption "unified system health reporting";
    outputDir = mkStrOption "/var/lib/system-report" "Directory for report output.";
    retentionDays = mkIntOption 30 "Days to keep historical reports.";
    features = lib.mkOption {
      type = lib.types.attrsOf lib.types.str;
      default = { };
      description = ''
        Feature flags exported to report scripts.
        Written by: loki.nix, scrutiny.nix, netdata.nix, secure-boot.nix,
        security/fail2ban.nix, opensnitch.nix, prometheus-grafana.
      '';
    };
  };
}
