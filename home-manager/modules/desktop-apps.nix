# User desktop apps without extra extensions or OBS plugins.

{ pkgs, ... }:

{
  home.packages = [
    pkgs.google-chrome
    pkgs.obs-studio
    pkgs.sqlitebrowser
    pkgs.telegram-desktop
  ];
}
