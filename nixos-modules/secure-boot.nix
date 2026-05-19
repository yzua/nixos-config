# Secure Boot preparation with sbctl.
# Provides tamper-evident boot chain to prevent evil-maid attacks.
#
# ACTIVATION STEPS (must be done manually after nixos-rebuild):
#   1. sudo sbctl create-keys          # Generate signing keys
#   2. sudo sbctl enroll-keys --microsoft  # Enroll keys in firmware (with Microsoft certs for dual-boot)
#   3. sudo sbctl status               # Verify enrollment
#   4. sudo sbctl verify               # Check which binaries need signing
#   5. sudo sbctl sign -s /boot/EFI/BOOT/BOOTX64.EFI
#   6. sudo sbctl sign -s /boot/EFI/systemd/systemd-bootx64.efi
#   7. sudo sbctl sign -s /boot/EFI/nixos/<kernel>.efi
#   8. sudo sbctl sign -s /boot/EFI/nixos/<initrd>.efi
#   9. Reboot, enter BIOS, enable Secure Boot in "Setup Mode"
#  10. Verify: sudo mokutil --sb-state

{
  config,
  lib,
  pkgsStable,
  systemdHelpers,
  ...
}:

let
  inherit (systemdHelpers) mkServiceHardening;
  cfg = config.mySystem.secureBoot;

  secureBootVerify = pkgsStable.writeShellScriptBin "secure-boot-verify" ''
    set -u

    sb_state="$(${pkgsStable.mokutil}/bin/mokutil --sb-state 2>&1)"
    echo "$sb_state"

    echo
    ${pkgsStable.sbctl}/bin/sbctl status

    echo
    if ! ${pkgsStable.sbctl}/bin/sbctl verify; then
      if printf '%s\n' "$sb_state" | grep -qi 'SecureBoot enabled'; then
        echo "Secure Boot is enabled, but sbctl verification failed." >&2
        exit 1
      fi

      echo "Secure Boot is not enabled yet; complete firmware enrollment before treating this host as verified." >&2
    fi
  '';
in
{
  options.mySystem.secureBoot = {
    enable = lib.mkEnableOption "Secure Boot preparation with sbctl";
  };

  config = lib.mkIf cfg.enable {
    mySystem.systemReport.features.HAS_SECURE_BOOT = lib.boolToString true;
    environment.systemPackages = [
      pkgsStable.sbctl
      pkgsStable.mokutil # MOK (Machine Owner Key) management
      secureBootVerify
    ];

    # Ensure sbctl keys directory exists with proper permissions
    systemd.tmpfiles.rules = [
      "d /var/lib/sbctl 0700 root root -"
    ];

    # Auto-sign EFI binaries after NixOS rebuilds
    # This runs after every boot to catch newly installed kernels
    systemd.services = {
      sbctl-sign = {
        description = "Auto-sign EFI binaries with Secure Boot keys";
        wantedBy = [ "multi-user.target" ];
        after = [ "local-fs.target" ];
        path = [ pkgsStable.sbctl ];

        script = ''
          # Only sign if keys exist and Secure Boot is enrolled
          if sbctl status 2>/dev/null | grep -q "Setup Mode: Disabled"; then
            # Sign all unsigned EFI binaries in /boot
            sbctl sign-all 2>/dev/null || true
            echo "[$(date -Iseconds)] Secure Boot: signed all EFI binaries" | \
              logger -t sbctl-sign
          fi
        '';

        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        }
        // mkServiceHardening {
          readWritePaths = [
            "/boot"
            "/var/lib/sbctl"
          ];
          protectHome = true;
        };
      };

      secure-boot-verify = {
        description = "Verify Secure Boot state and sbctl signatures";
        wantedBy = [ "multi-user.target" ];
        after = [ "sbctl-sign.service" ];
        requires = [ "sbctl-sign.service" ];
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${secureBootVerify}/bin/secure-boot-verify";
        };
      };
    };
  };
}
