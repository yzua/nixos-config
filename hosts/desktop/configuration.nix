# Desktop workstation: gaming, NVIDIA GPU, ethernet.

{ ... }:

{
  imports = [
    ./hardware-configuration.nix
    ../../nixos-modules
    ./modules
  ];

  mySystem = {
    hostProfile = "desktop";
    waydroid.enable = false;
    flatpak.enable = false;
    kdeconnect.enable = false; # Desktop has no Bluetooth adapter; avoids repetitive Bluez warnings.
    opensnitch.enable = false;
    i2pd.enable = true;
    yggdrasil.enable = true;
    vnc = {
      enable = false;
      tools.enable = true;
    };
    webRe.enable = true;
  };

  # LUKS unlock for root only — swap disabled (use zram only).
  # Swapping to encrypted disk caused freezes under heavy I/O (same disk as root).
  # Laptop already uses swapDevices = []; — matching that config.
  boot.initrd.luks.devices."luks-5e77e20c-28e2-4012-bc2a-c4c02acf3aab".allowDiscards = true;

  services.avahi.allowInterfaces = [ "eno1" ];
}
