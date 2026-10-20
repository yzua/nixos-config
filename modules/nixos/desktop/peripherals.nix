# Enable gaming-mouse controls and narrowly scoped USB configuration permissions.

{
  lib,
  pkgs,
  setup,
  ...
}:

let
  gpuOpenRGB = import ./openrgb-gpu-experiment.nix { inherit pkgs; };
in
{
  services.ratbagd.enable = true;

  # Tested exact-ID derivative, not a replacement for the user's USB-only GUI.
  # Order after RAM including its cleanup, avoiding i2c-dev ownership races in
  # the normal boot transaction. Neither helper is a general concurrent API.
  systemd.services.gpu-lighting = {
    description = "Restore experimentally validated MSI GPU static-white lighting";
    wantedBy = [ "multi-user.target" ];
    wants = [ "ram-lighting.service" ];
    after = [
      "ram-lighting.service"
      "systemd-modules-load.service"
      "systemd-udevd.service"
    ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      TimeoutStartSec = 360;
      TimeoutStopSec = 30;
      RuntimeDirectory = "gpu-lighting";
      RuntimeDirectoryMode = "0700";
      UMask = "0077";
      NoNewPrivileges = true;
      ProtectHome = true;
      ProtectSystem = "strict";
      PrivateTmp = true;
      ProtectControlGroups = true;
      ExecStart = lib.escapeShellArgs [
        "${pkgs.python3}/bin/python3"
        (toString ./gpu-lighting.py)
        (toString (pkgs.writeText "gpu-lighting.json" (builtins.toJSON setup.peripherals.gpu)))
        (lib.getExe gpuOpenRGB)
        "${pkgs.bubblewrap}/bin/bwrap"
        "${pkgs.kmod}/bin/modprobe"
        (toString ./ram-lighting.py)
      ];
      ExecStopPost = lib.escapeShellArgs [
        "${pkgs.python3}/bin/python3"
        (toString ./ram-lighting.py)
        "--cleanup"
        "${pkgs.kmod}/bin/modprobe"
      ];
    };
  };

  # ENE discovery writes lighting-controller addresses. This explicitly approved
  # boot operation is separate from USB controls and never grants user bus ACLs.
  systemd.services.ram-lighting = {
    description = "Restore static-white ENE RAM lighting on the verified adapter";
    wantedBy = [ "multi-user.target" ];
    after = [
      "systemd-modules-load.service"
      "systemd-udevd.service"
    ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      TimeoutStartSec = 360;
      TimeoutStopSec = 30;
      RuntimeDirectory = "ram-lighting";
      RuntimeDirectoryMode = "0700";
      UMask = "0077";
      NoNewPrivileges = true;
      ProtectHome = true;
      ProtectSystem = "strict";
      PrivateTmp = true;
      ProtectControlGroups = true;
      # ProtectKernelTunables masks /proc paths and prevents bubblewrap from
      # mounting the private /proc required to isolate raw device access.
      # No PrivateDevices/ProtectKernelModules: the parent must resolve the
      # host adapter and load i2c-dev. OpenRGB itself gets only one device node.
      ExecStart = lib.escapeShellArgs [
        "${pkgs.python3}/bin/python3"
        (toString ./ram-lighting.py)
        (toString (pkgs.writeText "ram-lighting.json" (builtins.toJSON setup.peripherals.ram)))
        (lib.getExe pkgs.openrgb)
        "${pkgs.bubblewrap}/bin/bwrap"
        "${pkgs.kmod}/bin/modprobe"
      ];
      # Also runs after failure/timeouts; never force-unload another bus user.
      ExecStopPost = lib.escapeShellArgs [
        "${pkgs.python3}/bin/python3"
        (toString ./ram-lighting.py)
        "--cleanup"
        "${pkgs.kmod}/bin/modprobe"
      ];
    };
  };

  # Apply active-seat ACLs before systemd's 73-seat-late.rules. Do not grant
  # blanket input/SMBus access, run an RGB server, or initialize cooler controls.
  services.udev.packages = [
    (pkgs.writeTextFile {
      name = "desktop-peripheral-permissions";
      destination = "/lib/udev/rules.d/70-desktop-peripherals.rules";
      text =
        lib.concatMapStringsSep "\n"
          (device: ''
            SUBSYSTEM=="hidraw", KERNEL=="hidraw*", ATTRS{idVendor}=="${device.vendorId}", ATTRS{idProduct}=="${device.productId}", TAG+="uaccess"
          '')
          [
            setup.peripherals.cooler
            setup.peripherals.lighting
          ];
    })
  ];
}
