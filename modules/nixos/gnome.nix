# Opt-in GNOME desktop stack: input method, login, printing, and audio.

{
  # GNOME uses IBus for input management; the English/Arabic XKB sources
  # themselves are configured per user in Home Manager.
  i18n.inputMethod = {
    enable = true;
    type = "ibus";
  };

  services.displayManager.gdm.enable = true;
  services.desktopManager.gnome.enable = true;

  # Fallback for plain X11; GNOME's active input sources live in Home Manager.
  services.xserver.xkb = {
    layout = "us";
    variant = "";
  };

  services.printing.enable = true;

  services.pulseaudio.enable = false;
  security.rtkit.enable = true;
  services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    pulse.enable = true;
  };
}
