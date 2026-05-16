# Scrutiny SMART disk health monitoring with InfluxDB retention

{
  config,
  lib,
  pkgs,
  constants,
  systemdHelpers,
  ...
}:

let
  inherit (systemdHelpers)
    mkServiceHardening
    mkOneshotService
    mkPersistentTimer
    ;
  inherit (constants) localhost ports;
in
{
  options.mySystem.scrutiny = {
    enable = lib.mkEnableOption "Scrutiny SMART disk health monitoring dashboard";
  };

  config = lib.mkIf config.mySystem.scrutiny.enable {
    services = {
      scrutiny = {
        enable = true;
        openFirewall = false;

        settings = {
          web.listen = {
            host = localhost;
            port = ports.scrutiny;
          };
          log.level = "INFO";
        };

        collector = {
          enable = true;
          schedule = "daily";
        };
      };

      influxdb2.settings.http-bind-address = "${localhost}:${toString ports.influxdb}";
    };

    systemd =
      let
        waitScript = pkgs.writeShellScript "wait-for-scrutiny" ''
          for i in $(seq 1 30); do
            ${pkgs.curl}/bin/curl -sf http://${localhost}:${toString ports.scrutiny}/api/summary >/dev/null 2>&1 && exit 0
            sleep 2
          done
          echo "Scrutiny API not ready after 60s"
          exit 1
        '';
      in
      {
        services = {
          scrutiny-collector.serviceConfig =
            mkServiceHardening {
              protectHome = true;
              protectSystem = null;
              useMkForce = true;
            }
            // {
              ExecStartPre = [ "${waitScript}" ];
            };

          scrutiny-retention-cleanup = mkOneshotService {
            description = "Clean old Scrutiny InfluxDB data";
            execStart = "${pkgs.findutils}/bin/find /var/lib/influxdb2 -type f -name '*.tsm' -mtime +365 -delete";
          };

          scrutiny.serviceConfig = mkServiceHardening {
            readWritePaths = [ "/var/lib/scrutiny" ];
            protectHome = true;
            memoryMax = "128M";
            memoryHigh = "96M";
            useMkForce = true;
          };

          influxdb2.serviceConfig = mkServiceHardening {
            protectHome = true;
            memoryMax = "256M";
            memoryHigh = "192M";
            useMkForce = true;
          };
        };

        timers.scrutiny-retention-cleanup = mkPersistentTimer {
          description = "Monthly Scrutiny InfluxDB data cleanup";
          onCalendar = "monthly";
          randomizedDelaySec = "1h";
        };
      };

    mySystem.boot.deferServices = lib.mkIf config.mySystem.scrutiny.enable [
      "scrutiny"
      "influxdb2"
    ];
  };
}
