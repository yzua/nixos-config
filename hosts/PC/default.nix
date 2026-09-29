# PC host entry point: hardware, boot, account, and shared NixOS modules.

{ pkgs, setup, ... }:

{
  imports = [
    ./hardware-configuration.nix
    ./graphics.nix
    ../../modules/nixos/base.nix
    ../../modules/nixos/audio.nix
    ../../modules/nixos/gnome.nix
    ../../modules/nixos/gaming.nix
    ../../modules/nixos/niri.nix
    ../../modules/nixos/mullvad-vpn.nix
    ../../modules/nixos/netbird.nix
    ../../modules/nixos/tailscale.nix
    ../../modules/nixos/numtide-cache.nix
    ../../modules/nixos/tor.nix
    ../../modules/nixos/tor-mullvad-bypass.nix
  ];

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
  services.fwupd.enable = true;

  networking.hostName = setup.hostName;
  networking.networkmanager.enable = true;
  services.printing.enable = true;
  time.timeZone = setup.timeZone;

  # Zsh is this account's login shell; expose system package completions to it.
  programs.zsh.enable = true;
  environment.pathsToLink = [ "/share/zsh" ];

  users.users.${setup.username} = {
    isNormalUser = true;
    description = setup.username;
    shell = pkgs.zsh;
    extraGroups = [
      "networkmanager"
      "wheel"
    ];
  };

  system.stateVersion = setup.stateVersion.system;
}
