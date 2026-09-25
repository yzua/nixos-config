# Everyday CLI tools without shell-managed packages.

{ pkgs, ... }:

{
  home.packages = [
    pkgs.bat
    pkgs.btop
    pkgs.fd
    pkgs.jq
    pkgs.lazygit
    pkgs.ripgrep
  ];
}
