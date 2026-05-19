# Docker container engine with bridge networking.

{
  config,
  constants,
  lib,
  pkgsStable,
  user,
  ...
}:

{
  options.mySystem.docker = {
    enable = lib.mkEnableOption "Docker container engine with bridge networking";
  };

  config = lib.mkIf config.mySystem.docker.enable {
    boot.kernelModules = [
      "kvm" # intel/amd modules auto-detected
      "bridge"
      "br_netfilter"
      # ip_tables/iptable_* removed — not available as modules in kernel 6.18.
      # iptables-nft compat layer translates calls to nf_tables automatically.
      "xt_MASQUERADE"
      "xt_comment"
      "xt_connmark"
      "xt_mark"
      "nf_nat"
      "xt_addrtype"
      "overlay"
    ];

    boot.kernel.sysctl = {
      "net.bridge.bridge-nf-call-iptables" = true;
      "net.bridge.bridge-nf-call-ip6tables" = true;
      "net.ipv4.ip_forward" = true;
    };

    virtualisation.docker = {
      enable = true;
      enableOnBoot = true;
      rootless = {
        enable = false;
        setSocketVariable = true;
      };
      daemon.settings = {
        dns = [ constants.dockerBridge ];
        ipv6 = false;
        iptables = true;
      };
    };

    users.users."${user}".extraGroups = [
      "docker"
      "kvm"
    ];

    # Only enable GPU containers on desktop (Optimus laptops can't reliably passthrough)
    hardware.nvidia-container-toolkit.enable =
      config.mySystem.nvidia.enable && (config.mySystem.hostProfile == "desktop");

    # The CDI generator calls NVML which requires matching kernel/userspace nvidia
    # driver versions. During rebuilds the userspace updates immediately but the
    # kernel module stays pinned until reboot — so NVML init fails with "Driver/
    # library version mismatch". Treat exit 1 as success so rebuilds don't break;
    # the spec regenerates correctly on next boot when versions align again.
    systemd.services.nvidia-container-toolkit-cdi-generator = {
      stopIfChanged = false;
      restartIfChanged = false;
      serviceConfig.SuccessExitStatus = [
        0
        1
      ];
    };

    mySystem.mullvadVpn.lanServices = [ "docker" ];

    networking.firewall = {
      trustedInterfaces = [ "docker0" ];
      # Let Docker manage its own FORWARD/NAT chains.
      # NixOS firewall blocks forwarded traffic by default — this breaks Docker bridges.
      filterForward = false;
      # Docker bridge forwarding (iptables via nf_tables compat layer)
      extraCommands = ''
        # === Docker bridge forwarding ===
        iptables -A FORWARD -i docker0 -j ACCEPT
        iptables -A FORWARD -o docker0 -j ACCEPT
        iptables -A FORWARD -i br-+ -j ACCEPT
        iptables -A FORWARD -o br-+ -j ACCEPT
        iptables -A INPUT -i docker0 -j ACCEPT
        iptables -A INPUT -i br-+ -j ACCEPT
      '';
    };

    environment.systemPackages = [
      pkgsStable.nvidia-container-toolkit
      pkgsStable.nftables # Docker needs nft for old rule cleanup
    ];
  };
}
