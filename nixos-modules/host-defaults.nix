# Shared host profile defaults for all mySystem options.

{
  config,
  lib,
  ...
}:

let
  profile = config.mySystem.hostProfile;
  isDesktop = profile == "desktop";
  isLaptop = profile == "laptop";
  mkDefaultTrue = lib.mkDefault true;
  mkDefaultFalse = lib.mkDefault false;
in
{
  options.mySystem.hostProfile = lib.mkOption {
    type = lib.types.enum [
      "desktop"
      "laptop"
    ];
    example = "desktop";
    description = "Host profile type. Determines default values for hardware-dependent options like gaming and bluetooth.";
  };

  config = {
    mySystem = {
      cleanup.enable = mkDefaultTrue;
      flatpak.enable = mkDefaultTrue;
      mullvadVpn.enable = mkDefaultTrue;
      tor.enable = mkDefaultTrue;
      i2pd.enable = mkDefaultFalse;
      yggdrasil.enable = mkDefaultFalse;
      dnscryptProxy.enable = mkDefaultTrue;
      printing.enable = mkDefaultTrue;
      docker.enable = mkDefaultTrue;
      libvirt.enable = mkDefaultTrue;
      nautilus.enable = mkDefaultTrue;
      glance.enable = mkDefaultTrue;
      netdata.enable = mkDefaultTrue;
      nixLd.enable = mkDefaultTrue;
      opensnitch.enable = mkDefaultFalse;
      scrutiny.enable = mkDefaultTrue;
      waydroid.enable = mkDefaultTrue;
      kdeconnect.enable = mkDefaultTrue;
      greetd.enable = mkDefaultTrue;
      nvidia.enable = mkDefaultTrue;
      fwupd.enable = mkDefaultTrue;
      backup.enable = mkDefaultFalse; # Requires restic-password sops secret
      ntfy.enable = mkDefaultTrue;
      observability.enable = mkDefaultTrue;
      loki.enable = mkDefaultTrue;
      alloy.enable = mkDefaultTrue;
      systemReport.enable = mkDefaultTrue;
      fail2ban.enable = mkDefaultTrue; # fail2ban does NOT conflict with AppArmor (only auditd does)
      metadataScrubber.enable = mkDefaultTrue; # Auto-strip metadata from user files
      monitoring.enable = mkDefaultTrue; # System monitoring tools (iotop, sysstat, sensors, vnStat)
      aide.enable = mkDefaultTrue; # Weekly AIDE file integrity monitoring
      lynis.enable = mkDefaultTrue; # Weekly Lynis security audit
      secureBoot.enable = mkDefaultTrue; # Secure Boot preparation with sbctl
      firewall.enable = mkDefaultTrue; # Network firewall and hostname leak prevention
      opsec.enable = mkDefaultTrue; # Session lock, zram swap, Chrony NTS
      securityServices.enable = mkDefaultTrue; # dbus-broker and journald hardening
      vnc = {
        enable = mkDefaultFalse; # Remote-access service posture; keep disabled unless explicitly needed.
        tools.enable = mkDefaultFalse; # Localhost-only manual launcher.
      };
      android.enable = mkDefaultTrue; # Android Studio, emulator, ADB, Fastboot
      browserDeps.enable = mkDefaultTrue; # Chromium, Puppeteer headless browser deps
      webRe.enable = mkDefaultTrue; # Web reverse engineering tools

      # Profile-dependent defaults
      gaming = {
        enable = lib.mkDefault isDesktop;
        enableGamemode = lib.mkDefault isDesktop;
        enableGamescope = lib.mkDefault isDesktop;
      };
      bluetooth = {
        enable = lib.mkDefault isLaptop;
        powerOnBoot = mkDefaultFalse;
      };
    };
  };
}
