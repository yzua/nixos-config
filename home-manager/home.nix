# Standalone Home Manager entry point for this account and its user modules.

{ pkgs, ... }:

let
  githubEmail = "260740417+yzua@users.noreply.github.com";
  localCliPath = ''
    export PATH="$HOME/.npm-global/bin:$PATH"
    export PATH="$HOME/.opencode/bin:$PATH"
  '';
in
{
  imports = [
    ./modules/ai.nix
    ./modules/cli.nix
    ./modules/desktop-apps.nix
    ./modules/firefox.nix
    ./modules/gaming.nix
    ./modules/ghostty.nix
    ./modules/git.nix
    ./modules/gnome.nix
    ./modules/keepassxc.nix
    ./modules/mime.nix
    ./modules/secrets.nix
    ./modules/shell.nix
    ./modules/skills.nix
    ./modules/vesktop.nix
  ];

  # Account-specific Git identity; GitHub remotes use the account's noreply address.
  programs.git.settings.user = {
    name = "yz";
    email = "git.remarry972@simplelogin.com";
  };
  programs.git.includes = [
    {
      condition = "hasconfig:remote.*.url:https://github.com/**";
      contents.user.email = githubEmail;
    }
    {
      condition = "hasconfig:remote.*.url:git@github.com:*/**";
      contents.user.email = githubEmail;
    }
  ];

  home.username = "yz";
  home.homeDirectory = "/home/yz";
  home.stateVersion = "26.05";
  # Keep account-owned CLIs available in either interactive shell without
  # placing their mutable contents in the Nix store.
  programs.bash.bashrcExtra = localCliPath;
  programs.zsh.initContent = localCliPath;
  home.packages = [
    pkgs.gh
    pkgs.telegram-desktop
    pkgs.wl-clipboard
  ];

  programs.home-manager.enable = true;
}
