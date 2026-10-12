# Permit SOPS-selected private DNS/HTTPS through NetBird without bypassing Mullvad globally.

{
  config,
  lib,
  pkgs,
  ...
}:

let
  client = config.services.netbird.clients.default or null;
  enabled = client != null && config.services.mullvad-vpn.enable;
  unit = "netbird-mullvad-private";
  secret = "netbird-mullvad-private-endpoint";
  httpsSecret = "netbird-mullvad-private-https-endpoint";
  stateDirectory = "/run/${unit}";
  command =
    action:
    lib.escapeShellArgs [
      "${pkgs.python3}/bin/python3"
      "${./netbird-mullvad-private.py}"
      action
      client.interface
      config.sops.secrets.${secret}.path
      stateDirectory
      "${pkgs.nftables}/bin/nft"
      config.sops.secrets.${httpsSecret}.path
    ];
in
{
  assertions = [
    {
      assertion = client != null;
      message = "NetBird/Mullvad private access requires the default NetBird client.";
    }
    {
      assertion = config.services.mullvad-vpn.enable;
      message = "NetBird/Mullvad private access requires services.mullvad-vpn.enable.";
    }
  ];

  sops.secrets = lib.mkIf enabled {
    ${httpsSecret} = {
      sopsFile = ../../../secrets/netbird-mullvad.yaml;
      key = "private_https_ipv4";
      mode = "0400";
      restartUnits = [ "${unit}.service" ];
    };
    ${secret} = {
      sopsFile = ../../../secrets/netbird-mullvad.yaml;
      key = "private_service_ipv4";
      mode = "0400";
      restartUnits = [ "${unit}.service" ];
    };
  };

  systemd.services = lib.mkIf enabled {
    ${unit} = {
      description = "Allow scoped private NetBird traffic alongside Mullvad";
      wantedBy = [ "multi-user.target" ];
      before = [ "${client.service.name}.service" ];
      requiredBy = [ "${client.service.name}.service" ];
      after = [ "sops-install-secrets.service" ];
      requires = [ "sops-install-secrets.service" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = command "apply";
        ExecStop = command "revoke";
        RuntimeDirectory = unit;
        RuntimeDirectoryMode = "0700";
        # Keep revoked-flow guards and their root-private state until reboot.
        RuntimeDirectoryPreserve = "yes";
        UMask = "0077";
        NoNewPrivileges = true;
        CapabilityBoundingSet = [ "CAP_NET_ADMIN" ];
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictAddressFamilies = [
          "AF_UNIX"
          "AF_NETLINK"
        ];
        ReadWritePaths = [ stateDirectory ];
      };
    };
  };
}
