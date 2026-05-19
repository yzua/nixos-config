# Flatpak sandboxed application distribution with Flathub.
# SECURITY: Default overrides restrict Flatpak apps to VPN tunnel and limit filesystem access.

{
  config,
  lib,
  systemdHelpers,
  ...
}:

let
  inherit (systemdHelpers) mkServiceHardening;
in

{
  options.mySystem.flatpak = {
    enable = lib.mkEnableOption "Flatpak support for sandboxed applications";
  };

  config = lib.mkIf config.mySystem.flatpak.enable {
    services.flatpak.enable = true;

    mySystem.mullvadVpn.lanServices = [ "flatpak" ];

    systemd = {
      # SECURITY: Default Flatpak overrides — force network through VPN, restrict filesystem
      tmpfiles.rules = [
        "d /etc/flatpak/overrides 0755 root root -"
        # Global: share host network (uses system DNS/VPN), deny home filesystem by default
        ''f /etc/flatpak/overrides/global 0644 root root - [Context]\nshared=network;\nfilesystem=!home;\nfilesystem=!host;\n[Environment]\nDBUS_SESSION_BUS_ADDRESS=\n''
      ];

      services.add-flathub = {
        description = "Add Flathub remote";
        restartIfChanged = false; # Do not block nixos-rebuild on transient network/DNS failures
        wantedBy = [ ]; # Deferred — started by timer after boot to avoid network wait
        wants = [ "network-online.target" ];
        after = [
          "network-online.target"
          "dnscrypt-proxy.service"
          "flatpak-system.service"
        ];
        path = [ config.services.flatpak.package ];
        script = ''
          if ! flatpak --system remotes --columns=name | grep -qx flathub; then
            if ! getent hosts flathub.org >/dev/null; then
              echo "add-flathub: DNS not ready, will retry via timer/restart"
              exit 0
            fi
          fi

          flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
        '';
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          Restart = "on-failure";
          RestartSec = 10;
          RestartSteps = 3; # Required when RestartMaxDelaySec is set
          RestartMaxDelaySec = 60;
        }
        // mkServiceHardening { protectHome = true; };
      };

      # Start Flathub registration 2 minutes after boot (needs network + DNS)
      timers.add-flathub-deferred = {
        description = "Deferred Flathub registration";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "120s";
          Unit = "add-flathub.service";
        };
      };
    };
  };
}
