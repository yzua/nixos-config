# Set per-user GNOME input sources and expose Tweaks in both desktop sessions.

{ lib, pkgs, ... }:

{
  home.packages = [ pkgs.gnome-tweaks ];

  # Upstream limits its launcher entry to GNOME, Unity, and Pantheon.
  xdg.desktopEntries."org.gnome.tweaks" = {
    name = "GNOME Tweaks";
    comment = "Adjust GNOME appearance and preferences";
    exec = "${pkgs.gnome-tweaks}/bin/gnome-tweaks";
    icon = "org.gnome.tweaks";
    categories = [
      "GNOME"
      "GTK"
      "Settings"
      "Utility"
    ];
    terminal = false;
  };

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
