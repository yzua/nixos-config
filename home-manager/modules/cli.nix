# Everyday CLI tools without shell-managed packages.

{ pkgs, ... }:

{
  home.packages = [
    pkgs.ast-grep
    pkgs.bat
    pkgs.btop
    pkgs.choose
    pkgs.fd
    pkgs.ffmpeg
    pkgs.fx
    pkgs.hcloud
    pkgs.htmlq
    pkgs.imagemagick
    pkgs.jq
    pkgs.lazydocker
    pkgs.lazygit
    pkgs.microfetch
    pkgs.mitmproxy
    pkgs.nmap
    pkgs.openssl
    pkgs.openssl.dev
    pkgs.ripgrep
    pkgs.sd
    pkgs.tokei
    pkgs.tree
    pkgs.wireshark-cli
    pkgs.yq
    pkgs.yt-dlp
  ];
}
