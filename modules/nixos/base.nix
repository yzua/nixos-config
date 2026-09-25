# Shared NixOS basics: locale, Nix features, and system-wide tools.

{ pkgs, ... }:

{
  # Keep application language, dates, and numbers English on every host;
  # the Arabic keyboard layout is a Home Manager setting.
  i18n.defaultLocale = "en_US.UTF-8";

  programs.nix-ld.enable = true;

  nixpkgs.config.allowUnfree = true;
  nix.settings.experimental-features = [
    "nix-command"
    "flakes"
  ];
  environment.systemPackages = [
    pkgs.git
    pkgs.just
  ];
}
