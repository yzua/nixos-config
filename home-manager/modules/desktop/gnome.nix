# Set GNOME input sources, preserve tray support, and expose Tweaks in both sessions.

{
  lib,
  pkgs,
  setup,
  ...
}:

{
  home.packages = [
    pkgs.gnome-tweaks
    pkgs.gnomeExtensions.appindicator
  ];

  # NetBird, Blueman, and other tray apps need a watcher in GNOME.
  # Noctalia provides its own in Niri. Preserve the user's other extensions.
  home.activation.enableGnomeAppIndicator =
    lib.hm.dag.entryAfter
      [
        "dconfSettings"
        "linkGeneration"
      ]
      ''
        run ${lib.getExe pkgs.python3} - ${lib.getExe' pkgs.glib "gsettings"} \
          ${lib.escapeShellArg pkgs.gnomeExtensions.appindicator.extensionUuid} <<'PY'
        import ast
        import subprocess
        import sys

        gsettings, extension = sys.argv[1:]
        current = subprocess.check_output(
            [gsettings, "get", "org.gnome.shell", "enabled-extensions"], text=True
        ).strip()
        enabled = ast.literal_eval(current.removeprefix("@as "))
        if extension not in enabled:
            enabled.append(extension)
            subprocess.run(
                [gsettings, "set", "org.gnome.shell", "enabled-extensions", repr(enabled)],
                check=True,
            )
        PY
      '';

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
