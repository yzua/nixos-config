# Set per-user GNOME input sources and install Tweaks; system-wide IBus lives in NixOS.

{ lib, pkgs, ... }:

{
  home.packages = [ pkgs.gnome-tweaks ];

  # English (default) and Arabic, switchable in GNOME with Super+Space.
  dconf.settings."org/gnome/desktop/input-sources".sources = [
    (lib.hm.gvariant.mkTuple [
      "xkb"
      "us"
    ])
    (lib.hm.gvariant.mkTuple [
      "xkb"
      "ara"
    ])
  ];
}
