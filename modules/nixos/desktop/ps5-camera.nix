# Allow only the active local desktop user to load volatile PS5 camera firmware.

{ pkgs, ... }:

{
  # Run before 73-seat-late.rules so logind applies an active-seat device ACL.
  # Loading happens on demand in the user app, never as root or at login.
  services.udev.packages = [
    (pkgs.writeTextFile {
      name = "ps5-camera-permissions";
      destination = "/lib/udev/rules.d/70-ps5-camera.rules";
      text = ''
        SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTR{idVendor}=="05a9", ATTR{idProduct}=="0580", TAG+="uaccess"
      '';
    })
  ];
}
