# Start LibrePods minimized with the graphical session, using NixOS's capability wrapper.

{ lib, pkgs, ... }:

{
  # GNOME needs a tray watcher; Noctalia already provides one in Niri.
  home.packages = [ pkgs.gnomeExtensions.appindicator ];
  # Extension selection is mutable (including Stylix's user-theme hook).
  # Add ours without replacing other extensions already enabled by the user.
  home.activation.enableLibrePodsIndicator =
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

  # Override the package's PATH-based launcher so desktop launches also use the wrapper.
  xdg.desktopEntries."me.kavishdevar.librepods" = {
    name = "LibrePods";
    genericName = "AirPods controls";
    exec = "/run/wrappers/bin/librepods";
    icon = "me.kavishdevar.librepods";
    categories = [ "Utility" ];
  };

  # The application and its restricted Bluetooth capability belong to NixOS.
  # Login startup is a user preference; don't launch the unprivileged store binary.
  systemd.user.services.librepods = {
    Unit = {
      Description = "LibrePods AirPods controls";
      After = [ "graphical-session.target" ];
      PartOf = [ "graphical-session.target" ];
      ConditionPathIsExecutable = "/run/wrappers/bin/librepods";
      StartLimitIntervalSec = 60;
      StartLimitBurst = 3;
    };
    Service = {
      ExecStart = "/run/wrappers/bin/librepods --start-minimized";
      Restart = "on-failure";
      RestartSec = 5;
    };
    Install.WantedBy = [ "graphical-session.target" ];
  };
}
