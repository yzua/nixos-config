# Loki log aggregation server.

{
  config,
  lib,
  constants,
  systemdHelpers,
  ...
}:

let
  inherit (systemdHelpers) mkServiceHardening;
  inherit (constants) localhost ports;
in
{
  options.mySystem.loki = {
    enable = lib.mkEnableOption "Loki log aggregation";
  };

  config = lib.mkIf config.mySystem.loki.enable {
    services.loki = {
      enable = true;

      configuration = {
        auth_enabled = false; # Single-tenant, localhost only

        server = {
          http_listen_port = ports.loki;
          http_listen_address = localhost;
          grpc_listen_port = ports.loki-grpc;
          grpc_listen_address = localhost;
        };

        common = {
          path_prefix = "/var/lib/loki";
          storage.filesystem = {
            chunks_directory = "/var/lib/loki/chunks";
            rules_directory = "/var/lib/loki/rules";
          };
          replication_factor = 1;
          ring = {
            instance_addr = localhost;
            kvstore.store = "inmemory";
          };
          instance_interface_names = [ ]; # Skip interface detection (fails on NixOS)
          instance_addr = localhost;
        };

        schema_config = {
          configs = [
            {
              from = "2024-01-01";
              store = "tsdb";
              object_store = "filesystem";
              schema = "v13";
              index = {
                prefix = "index_";
                period = "24h";
              };
            }
          ];
        };

        limits_config = {
          retention_period = "720h"; # 30 days
          ingestion_rate_mb = 4;
          ingestion_burst_size_mb = 6;
        };

        compactor = {
          working_directory = "/var/lib/loki/compactor";
          retention_enabled = true;
          retention_delete_delay = "2h";
          delete_request_store = "filesystem";
        };
      };
    };

    # SECURITY: Systemd hardening directives + resource limits
    systemd.services.loki.serviceConfig = mkServiceHardening {
      readWritePaths = [ "/var/lib/loki" ];
      protectHome = true;
      useMkForce = true;
      memoryMax = "256M";
      memoryHigh = "192M";
    };

    # Alloy is always enabled alongside Loki (it ships logs to Loki)
    mySystem = {
      alloy.enable = lib.mkDefault true;
      systemReport.features.HAS_LOKI = lib.boolToString true;
      boot.deferServices = lib.mkIf config.mySystem.loki.enable [
        "loki"
        "alloy"
      ];
    };
  };
}
