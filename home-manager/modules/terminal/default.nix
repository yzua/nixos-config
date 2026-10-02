# Install everyday CLI tools and import terminal, shell, and Git configuration.

{ pkgs, setup, ... }:

{
  imports = [
    ./ghostty.nix
    (import ./git.nix { inherit (setup) gitIdentity; })
    ./shell.nix
  ];

  # Everyday CLI tools without shell-managed packages.
  home.packages = [
    pkgs.ast-grep
    pkgs.bat
    pkgs.btop
    pkgs.choose
    pkgs.fd
    pkgs.ffmpeg
    pkgs.fx
    pkgs.gh
    pkgs.hcloud
    pkgs.htmlq
    pkgs.imagemagick
    pkgs.jq
    pkgs.lazydocker
    pkgs.lazygit
    pkgs.microfetch
    pkgs.mitmproxy
    pkgs.nmap
    pkgs.nodejs
    pkgs.openssl
    pkgs.openssl.dev
    pkgs.pnpm
    pkgs.ripgrep
    pkgs.sd
    pkgs.tokei
    pkgs.tree
    pkgs.wireshark-cli
    pkgs.wl-clipboard
    pkgs.yq
    pkgs.yt-dlp
  ];

  # Opt out of gh usage telemetry; extensions have separate settings.
  home.sessionVariables.GH_TELEMETRY = "false";
}
