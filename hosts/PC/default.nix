# PC host entry point: hardware, boot, account, and shared NixOS modules.

{ pkgs, setup, ... }:

{
  imports = [
    ./hardware-configuration.nix
    ../../modules/nixos/graphics.nix
    ../../modules/nixos/base.nix
    ../../modules/nixos/desktop/audio.nix
    ../../modules/nixos/desktop/bluetooth.nix
    ../../modules/nixos/desktop/librepods.nix
    ../../modules/nixos/desktop/gnome.nix
    ../../modules/nixos/desktop/flatpak.nix
    ../../modules/nixos/gaming.nix
    ../../modules/nixos/desktop/niri.nix
    ../../modules/nixos/networking/mullvad-vpn.nix
    ../../modules/nixos/networking/netbird.nix
    ../../modules/nixos/networking/tailscale.nix
    ../../modules/nixos/numtide-cache.nix
    ../../modules/nixos/yubikey.nix
    ../../modules/nixos/networking/tor.nix
    ../../modules/nixos/networking/tor-mullvad-bypass.nix
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
