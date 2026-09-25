# Everyday CLI tools; shell integrations remain unmanaged.

{ pkgs, ... }:

{
  home.packages = [
    pkgs.bat
    pkgs.btop
    pkgs.fd
    pkgs.fzf
    pkgs.jq
    pkgs.lazygit
    pkgs.ripgrep
    pkgs.zoxide
  ];
}
