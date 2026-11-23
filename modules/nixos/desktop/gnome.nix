# Enable GNOME login, input methods, and the setup-selected X11 keyboard fallback.

{ pkgs, setup, ... }:

{
  # GNOME uses IBus; the user's XKB sources come from Home Manager.
  i18n.inputMethod = {
    enable = true;
    type = "ibus";
    ibus.engines = [
      # The pinned engine ships dictionaries but omits its Python spellchecker.
      # Extend the cached wrapper instead of rebuilding the upstream engine.
      (pkgs.ibus-engines.typing-booster.overrideAttrs (old: {
        buildCommand = old.buildCommand + ''
          for program in bin/emoji-picker libexec/ibus-{setup,engine}-typing-booster; do
            wrapProgram "$out/$program" \
              --prefix PYTHONPATH : ${pkgs.python3Packages.pyenchant}/${pkgs.python3.sitePackages}
          done
        '';
      }))
    ];
  };

  services.displayManager.gdm.enable = true;
  services.desktopManager.gnome.enable = true;

  # Fallback for plain X11; GNOME's active input sources live in Home Manager.
  services.xserver.xkb = {
    layout = builtins.head setup.keyboard.layouts;
    variant = "";
  };
}
