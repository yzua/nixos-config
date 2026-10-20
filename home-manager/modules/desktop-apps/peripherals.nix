# Peripheral controls and login lighting restoration; never initialize cooling.

{
  lib,
  pkgs,
  setup,
  ...
}:

let
  cooler = setup.peripherals.cooler;
  lightingPython = pkgs.python3.withPackages (python: [ python.liquidctl ]);
  usbLighting = pkgs.writeShellApplication {
    name = "restore-usb-lighting";
    text = ''
      exec ${lightingPython}/bin/python3 ${./usb-lighting.py} ${
        pkgs.writeText "usb-lighting.json" (
          builtins.toJSON {
            inherit (setup.peripherals) cooler lighting;
          }
        )
      }
    '';
  };
  openrgbUSB = pkgs.writeShellApplication {
    name = "openrgb-usb";
    runtimeInputs = [
      pkgs.bubblewrap
      pkgs.coreutils
      pkgs.util-linux
    ];
    text =
      lib.replaceStrings
        [ "@allowedDevices@" "@openrgb@" ]
        [
          (lib.concatMapStringsSep "|" (device: "${device.vendorId}:${device.productId}") [
            setup.peripherals.cooler
            setup.peripherals.lighting
          ])
          (lib.getExe pkgs.openrgb)
        ]
        (builtins.readFile ./openrgb-usb.sh);
  };
  coolerStatus = pkgs.writeShellApplication {
    name = "cooler-status";
    runtimeInputs = [ pkgs.liquidctl ];
    text = ''
      # Telemetry only: no initialize, speed, color or non-volatile writes.
      exec liquidctl --vendor 0x${cooler.vendorId} --product 0x${cooler.productId} status
    '';
  };
in
{
  home.packages = [
    pkgs.piper
    pkgs.openrgb
    pkgs.liquidctl
    coolerStatus
    openrgbUSB
    usbLighting
  ];

  systemd.user.services.usb-lighting = {
    Unit = {
      Description = "Restore white USB lighting with calibrated pump/block balance";
      After = [ "graphical-session.target" ];
      PartOf = [ "graphical-session.target" ];
    };
    Service = {
      Type = "oneshot";
      RemainAfterExit = true;
      TimeoutStartSec = 60;
      ExecStart = lib.getExe usbLighting;
    };
    Install.WantedBy = [ "graphical-session.target" ];
  };

  # liquidctl is a CLI; expose its read-only helper in the application launcher.
  xdg.desktopEntries.cooler-status = {
    name = "Cooler Status";
    comment = "Show coolant temperature and fan/pump readings without changing settings";
    exec = "${lib.getExe pkgs.ghostty} --gtk-single-instance=false --wait-after-command=true -e ${lib.getExe coolerStatus}";
    icon = "utilities-system-monitor";
    terminal = false;
    categories = [
      "System"
      "Monitor"
    ];
  };

  # Detect only on demand, with other raw devices hidden. --nodetect also
  # disables the GUI Rescan button, so it must not be used for this launcher.
  xdg.desktopEntries."org.openrgb.OpenRGB" = {
    name = "OpenRGB (USB lighting)";
    comment = "Lighting controls for the configured USB controllers only";
    # OpenRGB defaults the fan zone to zero LEDs; size it for both RGB fans.
    exec = ''${lib.getExe openrgbUSB} --gui --device "${cooler.openrgbName}" --zone 1 --size ${toString cooler.fanLedCount}'';
    icon = "OpenRGB";
    terminal = false;
    categories = [
      "Settings"
      "HardwareSettings"
    ];
  };
}
