# Early-2015 Intel MacBook Pro: model-specific hardware, coding lab, and private VPNs.

{
  pkgs,
  setup,
  ...
}:

{
  imports = [
    ./hardware-configuration.nix
    ../../modules/nixos/base.nix
    ../../modules/nixos/secrets.nix
    ../../modules/nixos/desktop/audio.nix
    ../../modules/nixos/desktop/bluetooth.nix
    ../../modules/nixos/desktop/gnome.nix
    ../../modules/nixos/desktop/niri.nix
    ../../modules/nixos/networking/mullvad-vpn.nix
    ../../modules/nixos/networking/netbird.nix
    ../../modules/nixos/networking/netbird-mullvad-private.nix
    ../../modules/nixos/networking/resolved-private-domains.nix
    ../../modules/nixos/networking/tailscale.nix
    ../../modules/nixos/numtide-cache.nix
  ];

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
  boot.loader.systemd-boot.configurationLimit = 5;

  networking.hostName = setup.hostName;
  networking.networkmanager.enable = true;
  time.timeZone = setup.timeZone;

  # Broadwell uses i915/Mesa; the i965 VA-API driver supplies video decoding.
  boot.initrd.kernelModules = [ "i915" ];
  hardware.graphics = {
    enable = true;
    extraPackages = [ pkgs.intel-vaapi-driver ];
  };
  hardware.facetimehd.enable = true;
  services.xserver.videoDrivers = setup.graphics.videoDrivers;
  services.fstrim.enable = true;

  # Let the account enroll/control its own mesh client without shared node state.
  services.tailscale.extraSetFlags = [ "--operator=${setup.username}" ];
  services.libinput.enable = true;
  services.mbpfan.enable = true;
  services.upower.enable = true;
  services.power-profiles-daemon.enable = true;
  zramSwap.enable = true;

  # Keep remote administration available after the temporary bootstrap exits.
  services.openssh = {
    enable = true;
    settings = {
      PasswordAuthentication = false;
      KbdInteractiveAuthentication = false;
      PermitRootLogin = "no";
      AllowUsers = [ setup.username ];
    };
  };

  programs.zsh.enable = true;
  environment.pathsToLink = [ "/share/zsh" ];
  users.users.${setup.username} = {
    isNormalUser = true;
    description = setup.username;
    shell = pkgs.zsh;
    extraGroups = [
      "networkmanager"
      "wheel"
      "kvm"
    ];
  };

  system.stateVersion = setup.stateVersion.system;
}
