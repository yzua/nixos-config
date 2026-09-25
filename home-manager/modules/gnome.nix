# Set per-user GNOME keyboard sources; system-wide IBus lives in NixOS.

{ lib, ... }:

{
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
