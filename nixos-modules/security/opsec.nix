# Operational security (session locking, zram, NTS time).

{
  config,
  lib,
  ...
}:

{
  options.mySystem.opsec = {
    enable = lib.mkEnableOption "operational security (session lock, zram swap, Chrony NTS)";
  };

  config = lib.mkIf config.mySystem.opsec.enable {
    # Session lock on idle and lid-close — physical access protection
    # Chrony with NTS (authenticated time) replaces systemd-timesyncd
    services = {
      logind.settings.Login = {
        IdleAction = "lock";
        IdleActionSec = 300; # seconds
        HandleLidSwitch = "lock";
        HandleLidSwitchExternalPower = "lock";
        HandleLidSwitchDocked = "lock";
      };

      timesyncd.enable = lib.mkForce false;
      chrony = {
        enable = true;
        servers = [ ]; # NTS sources below instead of plain NTP
        extraConfig = ''
          server time.cloudflare.com iburst nts
          server nts.netnod.se iburst nts
          makestep 1.0 3
        '';
      };
    };

    # RAM-only swap — prevents sensitive data leaking to unencrypted partitions
    zramSwap = {
      enable = true;
      algorithm = "zstd";
      memoryPercent = 50;
    };
  };
}
