# PC host entry point: hardware, boot, account, and shared NixOS modules.

{
  imports = [
    ./hardware-configuration.nix
    ./graphics.nix
    ../../modules/nixos/base.nix
    ../../modules/nixos/development.nix
    ../../modules/nixos/gnome.nix
    ../../modules/nixos/gaming.nix
    ../../modules/nixos/mullvad-vpn.nix
    ../../modules/nixos/numtide-cache.nix
  ];

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "PC";
  networking.networkmanager.enable = true;
  # Etc/GMT signs are reversed: GMT-3 is a fixed UTC+03:00, with no DST.
  time.timeZone = "Etc/GMT-3";

  users.users."yz" = {
    isNormalUser = true;
    description = "yz";
    extraGroups = [
      "networkmanager"
      "wheel"
    ];
  };

  # Keep the version from the initial install; it is not the Nixpkgs release.
  system.stateVersion = "26.05";
}
