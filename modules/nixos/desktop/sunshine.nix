# Unprivileged Wayland streaming to explicit laptop/TV LAN clients, with encryption.

{
  config,
  lib,
  pkgs,
  setup,
  ...
}:

let
  remote = setup.remoteDesktop;
  interface = lib.escapeShellArg remote.hostInterface;
  destination = lib.escapeShellArg remote.hostAddress;
  clients = [
    remote.clientAddress
    remote.tv.clientAddress
  ];
  monitor = lib.findFirst (output: output.primary) (builtins.head setup.monitors) setup.monitors;
  # Sunshine's Boost.Process command parser does not understand POSIX single
  # quotes. Pass a bare script path, and keep shell-escaped arguments in Bash.
  setMode =
    mode:
    toString (
      pkgs.writeShellScript "sunshine-tv-mode-${lib.strings.sanitizeDerivationName mode}" ''
        exec ${lib.getExe pkgs.niri} msg output ${lib.escapeShellArg monitor.match} mode ${lib.escapeShellArg mode}
      ''
    );
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
      controller = "enabled";
      # Standard XInput mapping works across Steam/Proton games, even when the
      # physical client controller is a DualSense paired with the TV.
      gamepad = "x360";
    };
    applications.apps = [
      { name = remote.appName; }
      {
        name = remote.tv.appName;
        prep-cmd = [
          {
            do = setMode remote.tv.mode;
            undo = setMode monitor.mode;
          }
        ];
        detached = [ "${lib.getExe config.programs.steam.package} -bigpicture" ];
      }
    ];
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
  networking.firewall.extraCommands = lib.concatMapStringsSep "\n" (
    client:
    let
      source = lib.escapeShellArg "${client}/32";
      rules = "-i ${interface} -s ${source} -d ${destination}";
    in
    ''
      iptables -A nixos-fw ${rules} -p tcp -m multiport --dports 47984,47989,48010 -j nixos-fw-accept
      iptables -A nixos-fw ${rules} -p udp -m multiport --dports 47998:48000 -j nixos-fw-accept
    ''
  ) clients;
}
