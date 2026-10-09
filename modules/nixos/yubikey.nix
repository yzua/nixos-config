# PC/SC and USB access for the user's YubiKey tools and authenticator codes.

{ pkgs, ... }:

{
  services.pcscd.enable = true;
  # Supply Yubico's USB permission rules without installing user apps system-wide.
  services.udev.packages = [ pkgs.yubikey-personalization ];
}
