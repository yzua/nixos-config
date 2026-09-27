# Opt-in GNOME desktop stack: input method, login, and printing.

{ setup, ... }:

{
  # GNOME uses IBus; the user's XKB sources come from Home Manager.
  i18n.inputMethod = {
    enable = true;
    type = "ibus";
  };

  services.displayManager.gdm.enable = true;
  services.desktopManager.gnome.enable = true;

  # Fallback for plain X11; GNOME's active input sources live in Home Manager.
  services.xserver.xkb = {
    layout = builtins.head setup.keyboard.layouts;
    variant = "";
  };
}
