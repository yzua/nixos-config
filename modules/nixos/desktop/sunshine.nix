# Unprivileged Wayland desktop streaming to one IPv4 LAN client, with encryption.

{
  lib,
  pkgs,
  setup,
  ...
}:

let
  remote = setup.remoteDesktop;
  interface = lib.escapeShellArg remote.hostInterface;
  source = lib.escapeShellArg "${remote.clientAddress}/32";
  destination = lib.escapeShellArg remote.hostAddress;
  rules = "-i ${interface} -s ${source} -d ${destination}";
in
{
  services.sunshine = {
    enable = true;
    autoStart = true;
    openFirewall = false;
    # The cached non-CUDA build cannot complete its NVENC frame conversion test.
    package = pkgs.sunshine.override { cudaSupport = true; };
    # Niri implements the screencopy protocol; no privileged KMS wrapper needed.
    capSysAdmin = false;
    settings = {
      sunshine_name = setup.hostName;
      address_family = "ipv4";
      # Keep loopback available for the local-only administration interface.
      origin_web_ui_allowed = "pc";
      upnp = "disabled";
      lan_encryption_mode = 2;
      wan_encryption_mode = 2;
      capture = "wlr";
      encoder = "nvenc";
      controller = "disabled";
    };
    applications.apps = [ { name = remote.appName; } ];
  };

  # Preserve the desktop's existing Avahi discovery without enabling publishing.
  # Moonlight pairs by address, so Sunshine does not need service announcements.
  services.avahi.publish = {
    enable = lib.mkForce false;
    userServices = lib.mkForce false;
  };

  systemd.user.services.sunshine = {
    unitConfig.ConditionUser = setup.username;
    serviceConfig.UMask = "0077";
  };

  # Never use the module's global port openings, nor expose its web UI (47990).
  # Explicit unicast pairing needs no additional discovery firewall openings.
  networking.firewall.extraCommands = ''
    iptables -A nixos-fw ${rules} -p tcp -m multiport --dports 47984,47989,48010 -j nixos-fw-accept
    iptables -A nixos-fw ${rules} -p udp -m multiport --dports 47998:48000 -j nixos-fw-accept
  '';
}
