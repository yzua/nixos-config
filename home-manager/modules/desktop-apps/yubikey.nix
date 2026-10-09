# Yubico Authenticator and the YubiKey management CLI for this user.

{ pkgs, ... }:

{
  home.packages = [
    pkgs.yubioath-flutter
    pkgs.yubikey-manager
  ];
}
