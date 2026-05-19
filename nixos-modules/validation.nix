# Cross-module conflict assertions and dependency validation.

{
  config,
  constants,
  lib,
  ...
}:

let
  inherit (constants) localhost;
  inherit
    (import ../shared/_secret-check.nix {
      inherit lib;
      rootDir = ../.;
    })
    hasSecret
    ;
in

{
  assertions = [
    # === Power Management Daemon Conflicts ===
    {
      assertion = !(config.services.tlp.enable && config.services.power-profiles-daemon.enable);
      message = "TLP and power-profiles-daemon cannot be enabled simultaneously. Choose one power management daemon.";
    }

    {
      assertion = !(config.services.power-profiles-daemon.enable && config.services.thermald.enable);
      message = "power-profiles-daemon and thermald cannot be enabled simultaneously. They both manage thermal/power profiles.";
    }

    # === Audio Stack Conflicts ===
    {
      assertion = !(config.services.pulseaudio.enable && config.services.pipewire.enable);
      message = "PulseAudio and PipeWire cannot be enabled simultaneously. PipeWire provides a modern replacement for PulseAudio.";
    }

    # === Graphics Driver Conflicts ===
    {
      assertion = !(lib.elem "nouveau" config.boot.kernelModules && config.hardware.nvidia.enable);
      message = "NVIDIA proprietary and nouveau open-source drivers cannot coexist. Remove nouveau from boot.kernelModules.";
    }

    # === Gaming System Dependencies ===
    {
      assertion = !config.mySystem.gaming.enable || config.hardware.graphics.enable;
      message = "Gaming requires hardware.graphics.enable = true. Graphics drivers must be configured.";
    }

    {
      assertion = !config.mySystem.gaming.enable || config.services.pipewire.pulse.enable;
      message = "Gaming requires PipeWire with PulseAudio compatibility layer (services.pipewire.pulse.enable = true).";
    }

    # === VPN/Network Dependencies ===
    {
      assertion = !config.mySystem.mullvadVpn.enable || config.networking.networkmanager.enable;
      message = "Mullvad VPN requires NetworkManager (networking.networkmanager.enable = true).";
    }

    # === Network Service Security ===
    {
      assertion = !config.services.avahi.enable || config.services.avahi.allowInterfaces != [ ];
      message = "Avahi must have explicit allowInterfaces list for security. Don't expose mDNS on all interfaces.";
    }

    {
      assertion = !config.mySystem.dnscryptProxy.enable || !config.services.resolved.enable;
      message = "DNSCrypt-Proxy and systemd-resolved cannot both manage DNS. Disable resolved when using DNSCrypt.";
    }

    # === Display Manager Conflicts ===
    {
      assertion = !(config.services.displayManager.gdm.enable && config.services.greetd.enable);
      message = "GDM and greetd cannot be enabled simultaneously. Choose one display manager.";
    }

    # === Observability Stack Dependencies ===
    # Moved to prometheus-grafana/_validation.nix (module-registered assertions)

    # === Local Dashboard Bindings ===
    {
      assertion =
        !config.mySystem.glance.enable || config.services.glance.settings.server.host == localhost;
      message = "Glance must bind to localhost. Set services.glance.settings.server.host = constants.localhost.";
    }

    {
      assertion =
        !config.mySystem.netdata.enable || config.services.netdata.config.global."bind to" == localhost;
      message = "Netdata must bind to localhost. Set services.netdata.config.global.\"bind to\" = constants.localhost.";
    }

    {
      assertion =
        !config.mySystem.scrutiny.enable || config.services.scrutiny.settings.web.listen.host == localhost;
      message = "Scrutiny must bind to localhost. Set services.scrutiny.settings.web.listen.host = constants.localhost.";
    }

    {
      assertion =
        !config.mySystem.scrutiny.enable
        ||
          config.services.influxdb2.settings.http-bind-address
          == "${localhost}:${toString constants.ports.influxdb}";
      message = "Scrutiny's InfluxDB must bind to localhost. Set services.influxdb2.settings.http-bind-address to constants.localhost.";
    }

    {
      assertion =
        !config.mySystem.loki.enable
        || config.services.loki.configuration.server.http_listen_address == localhost;
      message = "Loki HTTP must bind to localhost. Set services.loki.configuration.server.http_listen_address = constants.localhost.";
    }

    {
      assertion =
        !config.mySystem.loki.enable
        || config.services.loki.configuration.server.grpc_listen_address == localhost;
      message = "Loki gRPC must bind to localhost. Set services.loki.configuration.server.grpc_listen_address = constants.localhost.";
    }

    # === Enabled Feature Secret Inventory ===
    # grafana_admin_password and ntfy_topic checks moved to prometheus-grafana/_validation.nix

    {
      assertion = !config.mySystem.systemReport.enable || hasSecret "noctalia_location";
      message = "Noctalia/system-report integration expects noctalia_location in secrets/secrets.yaml.";
    }

    {
      assertion =
        hasSecret "zai_api_key"
        && hasSecret "openrouter_api_key"
        && hasSecret "context7_api_key"
        && hasSecret "gemini_api_key"
        && hasSecret "zellij_web_password";
      message = "AI agent configuration requires zai_api_key, openrouter_api_key, context7_api_key, gemini_api_key, and zellij_web_password in secrets/secrets.yaml.";
    }
  ];

  warnings = lib.optional (builtins.pathExists /etc/nixos/configuration.nix) ''
    Legacy /etc/nixos/configuration.nix exists alongside your flake config.
    This file may conflict with your flake-based configuration (different kernel, GNOME vs niri, etc.).
    Consider removing it: sudo mv /etc/nixos/configuration.nix /etc/nixos/configuration.nix.bak
  '';
}
