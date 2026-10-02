# Set per-user GNOME input sources and expose Tweaks in both desktop sessions.

{
  lib,
  pkgs,
  setup,
  ...
}:

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

  # GNOME uses the same layouts declared for Niri in the flake setup.
  dconf.settings."org/gnome/desktop/input-sources".sources = map (
    layout:
    lib.hm.gvariant.mkTuple [
      "xkb"
      layout
    ]
  ) setup.keyboard.layouts;
}
