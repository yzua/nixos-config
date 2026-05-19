# Weekly Lynis security audit timer and service.

{
  config,
  lib,
  pkgsStable,
  systemdHelpers,
  ...
}:

let
  inherit (systemdHelpers)
    mkServiceHardening
    mkOneshotService
    mkNixosTimer
    ;

  auditScript = pkgsStable.writeShellScript "security-audit.sh" ''
    #!${pkgsStable.bash}/bin/bash
    echo 'Running Lynis audit...'
    ${pkgsStable.lynis}/bin/lynis audit system --quiet
    echo 'Security audit completed!'
  '';
in

{
  options.mySystem.lynis = {
    enable = lib.mkEnableOption "weekly Lynis security audit";
  };

  config = lib.mkIf config.mySystem.lynis.enable {
    environment.systemPackages = [ pkgsStable.lynis ];

    systemd = {
      timers.security-audit = mkNixosTimer {
        description = "Weekly security audit";
        onCalendar = "weekly";
        unit = "security-audit.service";
      };

      services.security-audit = mkOneshotService {
        description = "Run Lynis security audit";
        execStart = auditScript;
        extraServiceConfig = mkServiceHardening {
          readWritePaths = [ "/tmp" ];
          # NOTE: PrivateNetwork omitted so Lynis can audit network config
        };
      };
    };
  };
}
