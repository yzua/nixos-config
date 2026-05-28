# Grafana Alloy log shipper for Loki.

{
  config,
  lib,
  constants,
  systemdHelpers,
  ...
}:

let
  inherit (systemdHelpers) mkServiceHardening;
  inherit (constants) urls;
in
{
  options.mySystem.alloy = {
    enable = lib.mkEnableOption "Grafana Alloy log shipper";
  };

  config = lib.mkIf config.mySystem.alloy.enable {
    services.alloy = {
      enable = true;
      extraFlags = [ "--disable-reporting" ];
    };

    environment.etc."alloy/config.alloy".text = ''
      loki.source.journal "journal" {
        max_age    = "12h"
        forward_to = [loki.write.default.receiver]
        relabel_rules = discovery.relabel.journal.rules
        labels = {
          job = "systemd-journal",
        }
      }

      discovery.relabel "journal" {
        targets = []

        rule {
          source_labels = ["__journal__systemd_unit"]
          target_label  = "unit"
        }

        rule {
          source_labels = ["__journal__hostname"]
          target_label  = "hostname"
        }

        rule {
          source_labels = ["__journal_priority_keyword"]
          target_label  = "level"
        }
      }

      loki.write "default" {
        endpoint {
          url = "${urls.loki}/loki/api/v1/push"
        }
        external_labels = {}
      }
    '';

    # SECURITY: Systemd hardening directives + resource limits
    systemd.services.alloy.serviceConfig =
      mkServiceHardening {
        protectHome = true;
        useMkForce = true;
        memoryMax = "128M";
        memoryHigh = "64M";
      }
      // {
        # Alloy 1.16 initializes wazero/go-re2 with executable mmap.
        MemoryDenyWriteExecute = lib.mkForce false;
      };
  };
}
