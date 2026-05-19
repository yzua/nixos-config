# Prometheus + Alertmanager + Grafana observability stack.

{ config, lib, ... }:

{
  imports = [
    ./_prometheus.nix # modules-check: manual-helper Prometheus + Alertmanager collection and alert routing
    ./_grafana.nix # modules-check: manual-helper Grafana dashboards and visualization
    ./_ntfy-bridge.nix # modules-check: manual-helper Alertmanager → ntfy.sh push notification bridge
    ./_validation.nix # modules-check: manual-helper Observability and ntfy assertions
  ];

  options.mySystem.observability = {
    enable = lib.mkEnableOption "Prometheus + Grafana observability stack";
  };

  config = lib.mkIf config.mySystem.observability.enable {
    mySystem.systemReport.features.HAS_PROMETHEUS = "true";
  };
}
