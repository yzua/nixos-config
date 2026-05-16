# Grafana visualization and dashboard provisioning.

{
  config,
  constants,
  lib,
  pkgs,
  systemdHelpers,
  ...
}:

let
  inherit (systemdHelpers) mkServiceHardening;
  inherit (constants) localhost ports;

  helpers = import ./_helpers.nix { inherit constants; };
  inherit (helpers) datasources;

  dashboardDir = pkgs.runCommand "grafana-dashboards" { } ''
    mkdir -p $out
    cp ${./dashboards/system-overview.json} $out/system-overview.json
    cp ${./dashboards/log-errors.json} $out/log-errors.json
  '';
in
{
  config = lib.mkIf config.mySystem.observability.enable {
    sops.secrets.grafana_admin_password = {
      owner = "grafana";
      mode = "0400";
    };

    services.grafana = {
      enable = true;

      settings = {
        server = {
          http_addr = localhost;
          http_port = ports.grafana;
        };

        security = {
          admin_user = "admin";
          admin_password = "$__file{${config.sops.secrets.grafana_admin_password.path}}";
          secret_key = "$__file{${config.sops.secrets.grafana_admin_password.path}}"; # TODO: use a dedicated grafana_secret_key sops secret — reusing admin_password means rotating it breaks encrypted datasources
        };

        "auth.anonymous".enabled = false;
        analytics.reporting_enabled = false;
      };

      provision = {
        datasources.settings = {
          apiVersion = 1;
          deleteDatasources = map (ds: { inherit (ds) name orgId; }) datasources;
          inherit datasources;
        };

        dashboards.settings.providers = [
          {
            name = "default";
            options.path = dashboardDir;
          }
        ];
      };
    };

    systemd.services.grafana = {
      after = [
        "loki.service"
        "prometheus.service"
      ];
      requires = [ "prometheus.service" ];
      restartTriggers = [ config.sops.secrets.grafana_admin_password.path ];
      serviceConfig = mkServiceHardening {
        memoryMax = "256M";
        memoryHigh = "192M";
        protectHome = lib.mkDefault "read-only";
        protectSystem = lib.mkDefault "strict";
      };
    };

    mySystem.boot.deferServices = [ "grafana" ];
  };
}
