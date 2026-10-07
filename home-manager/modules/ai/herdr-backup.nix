# Keep private recovery layouts independently of Herdr and warn about stale running servers.
{
  aiPackages,
  config,
  lib,
  pkgs,
  ...
}:
let
  backup = pkgs.writeShellScript "herdr-layout-backup" ''
    exec ${lib.getExe pkgs.python3} ${./herdr-backup.py} \
      --config-dir ${lib.escapeShellArg "${config.xdg.configHome}/herdr"} \
      --state-dir ${lib.escapeShellArg "${config.xdg.stateHome}/herdr-layout-backups"} \
      "$@"
  '';
in
{
  home.activation.backupHerdrLayouts = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    if ! run ${backup} --check-server ${lib.getExe aiPackages.herdr}; then
      echo "WARNING: Herdr recovery backup failed; continuing activation without touching live sessions." >&2
    fi
  '';

  systemd.user.services.herdr-layout-backup = {
    Unit.Description = "Preserve private Herdr layout recovery copies";
    Service = {
      Type = "oneshot";
      TimeoutStartSec = "1min";
      ExecStart = "${backup}";
      UMask = "0077";
    };
  };
  systemd.user.timers.herdr-layout-backup = {
    Unit.Description = "Periodically preserve Herdr layouts";
    Timer = {
      OnStartupSec = "1min";
      OnUnitActiveSec = "5min";
      AccuracySec = "30s";
    };
    Install.WantedBy = [ "timers.target" ];
  };
}
