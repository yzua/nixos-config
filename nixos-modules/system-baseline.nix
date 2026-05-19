# System baseline: always-on settings for every host.
# These are fundamental infrastructure that every machine needs regardless of profile.

{ lib, ... }:

{
  # Timezone (UTC+3, POSIX sign reversed for privacy)
  time.timeZone = "Etc/GMT-3";

  services = {
    # X server for XWayland compatibility on Niri (Wayland)
    # Keyboard layout configured in i18n.nix
    xserver.enable = true;

    # Battery and power monitoring
    upower.enable = true;

    # TrackPoint scroll emulation (middle-button + TrackPoint = scroll)
    libinput = {
      enable = true;
      mouse = {
        middleEmulation = true;
        scrollMethod = "button";
        scrollButton = 2; # BTN_MIDDLE
      };
    };

    # SSD trimming
    fstrim = {
      enable = true;
      interval = "weekly";
    };

    # OOM protection
    earlyoom = {
      enable = true;
      freeMemThreshold = 15; # 15% ≈ 4.8GB on 32GB — act earlier to prevent compositor stalls
      freeSwapThreshold = 15;
      enableNotifications = true; # Desktop notification on kill
    };

    # Resolve conflict: earlyoom sets systembus-notify=true, smartd (via Scrutiny) sets false.
    # We want notifications enabled for earlyoom OOM-kill alerts.
    systembus-notify.enable = lib.mkForce true;
  };
}
