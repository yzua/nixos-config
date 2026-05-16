# Prometheus + Alertmanager time-series collection and alert routing.

{
  config,
  constants,
  lib,
  systemdHelpers,
  ...
}:

let
  inherit (systemdHelpers) mkServiceHardening;
  inherit (constants) localhost ports;

  helpers = import ./_helpers.nix { inherit constants; };
  inherit (helpers)
    mkStaticConfig
    netdataTarget
    lokiTarget
    alertmanagerTarget
    ;
in
{
  config = lib.mkIf config.mySystem.observability.enable {
    services.prometheus = {
      enable = true;
      port = ports.prometheus;
      listenAddress = localhost;

      globalConfig = {
        scrape_interval = "30s"; # 30s sufficient for personal machine (halves disk/CPU vs 15s default)
        evaluation_interval = "30s";
      };

      scrapeConfigs = [
        {
          job_name = "netdata";
          metrics_path = "/api/v1/allmetrics";
          params.format = [ "prometheus" ];
          static_configs = mkStaticConfig [ netdataTarget ];
        }
        {
          job_name = "loki";
          static_configs = mkStaticConfig [ lokiTarget ];
        }
      ];

      rules = import ./alert-rules.nix;

      alertmanagers = [
        {
          static_configs = mkStaticConfig [ alertmanagerTarget ];
        }
      ];

      extraFlags = [
        "--storage.tsdb.retention.time=30d"
        "--storage.tsdb.retention.size=10GB"
      ];

      alertmanager = {
        enable = true;
        listenAddress = localhost;
        port = ports.alertmanager;
        extraFlags = [
          "--cluster.listen-address="
        ];

        # Route all alerts via alertmanager-ntfy bridge → ntfy.sh
        configuration = {
          route = {
            receiver = "ntfy";
            group_by = [
              "alertname"
              "severity"
            ];
            group_wait = "30s";
            group_interval = "5m";
            repeat_interval = "4h";
          };
          receivers = [
            {
              name = "ntfy";
              webhook_configs = [
                {
                  url = "http://${localhost}:${toString config.mySystem.ntfy.port}/hook";
                  send_resolved = true;
                }
              ];
            }
          ];
        };
      };
    };

    systemd.services = {
      prometheus.serviceConfig = mkServiceHardening {
        memoryMax = "512M";
        memoryHigh = "384M";
        protectHome = lib.mkDefault "read-only";
        protectSystem = lib.mkDefault "strict";
      };
      alertmanager.serviceConfig = mkServiceHardening {
        memoryMax = "128M";
        memoryHigh = "64M";
        protectHome = lib.mkDefault "read-only";
      };
    };

    mySystem.boot.deferServices = [ "prometheus" ];
  };
}
