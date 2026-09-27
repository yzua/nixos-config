# Shared NixOS basics: locale, Nix features, and system-wide tools.

{ pkgs, setup, ... }:

{
  i18n.defaultLocale = setup.locale;

  programs.nix-ld.enable = true;

  nixpkgs.config.allowUnfree = true;
  nix.settings.experimental-features = [
    "nix-command"
    "flakes"
  ];
  # Collect unreachable store paths without pruning rollback generations.
  nix.gc = {
    automatic = true;
    dates = "weekly";
  };
  environment.systemPackages = [
    pkgs.git
    pkgs.just
  ];
}
