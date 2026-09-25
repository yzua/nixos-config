{ lib, pkgs, ... }:

{
  home.username = "yz";
  home.homeDirectory = "/home/yz";
  home.stateVersion = "26.05";
  home.packages = [ pkgs.telegram-desktop ];

  programs.home-manager.enable = true;

  # English (default) and Arabic, switchable in GNOME with Super+Space.
  dconf.settings."org/gnome/desktop/input-sources".sources = [
    (lib.hm.gvariant.mkTuple [ "xkb" "us" ])
    (lib.hm.gvariant.mkTuple [ "xkb" "ara" ])
  ];
}
