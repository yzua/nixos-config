# Observability stack validation assertions and secret checks.
# Imported by prometheus-grafana/default.nix alongside the config modules.

{
  config,
  constants,
  lib,
  ...
}:

let
  inherit (constants) localhost;
  inherit
    (import ../../shared/_secret-check.nix {
      inherit lib;
      rootDir = ../..;
    })
    hasSecret
    ;

  observabilityAssertions = lib.optionals config.mySystem.observability.enable [
    {
      assertion = config.mySystem.loki.enable;
      message = "Observability stack requires Loki (mySystem.loki.enable = true) for log aggregation. Grafana provisions a Loki datasource that would be unreachable without it.";
    }
    {
      assertion = config.services.prometheus.listenAddress == localhost;
      message = "Prometheus must bind to localhost. Set services.prometheus.listenAddress = constants.localhost.";
    }
    {
      assertion = config.services.prometheus.alertmanager.listenAddress == localhost;
      message = "Alertmanager must bind to localhost. Set services.prometheus.alertmanager.listenAddress = constants.localhost.";
    }
    {
      assertion = config.services.grafana.settings.server.http_addr == localhost;
      message = "Grafana must bind to localhost. Set services.grafana.settings.server.http_addr = constants.localhost.";
    }
    {
      assertion = hasSecret "grafana_admin_password";
      message = "mySystem.observability.enable requires grafana_admin_password in secrets/secrets.yaml.";
    }
  ];

  ntfyAssertions = lib.optionals config.mySystem.ntfy.enable [
    {
      assertion = config.mySystem.observability.enable;
      message = "ntfy alert bridge requires observability stack (mySystem.observability.enable = true) for Alertmanager integration. Either enable observability or disable ntfy.";
    }
    {
      assertion = hasSecret "ntfy_topic";
      message = "mySystem.ntfy.enable requires ntfy_topic in secrets/secrets.yaml.";
    }
  ];
in
{
  config.assertions = observabilityAssertions ++ ntfyAssertions;
}
