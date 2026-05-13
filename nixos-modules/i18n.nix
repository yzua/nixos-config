# Internationalization, locale, input methods, and keyboard layout.

{
  constants,
  pkgs,
  ...
}:

let
  inherit (constants) locale;
  localeCategories = [
    "LC_ADDRESS"
    "LC_IDENTIFICATION"
    "LC_MEASUREMENT"
    "LC_MONETARY"
    "LC_NAME"
    "LC_NUMERIC"
    "LC_PAPER"
    "LC_TELEPHONE"
    "LC_TIME"
  ];
in
{
  i18n = {
    defaultLocale = locale;

    # PRIVACY: en_US for all categories to blend with largest English-speaking locale pool
    extraLocaleSettings = builtins.listToAttrs (
      map (name: {
        inherit name;
        value = locale;
      }) localeCategories
    );

    inputMethod = {
      enable = true;
      type = "fcitx5";

      fcitx5 = {
        waylandFrontend = true;

        addons = with pkgs; [
          fcitx5-gtk
          qt6Packages.fcitx5-configtool
          qt6Packages.fcitx5-chinese-addons
          fcitx5-anthy
        ];
      };
    };
  };

  services.xserver.xkb = {
    inherit (constants.keyboard) layout variant options;
  };

  # Keep the early boot LUKS prompt predictable. The graphical session still
  # gets the full XKB layout above, but initrd passphrase entry uses the VT map.
  console.keyMap = "us";

  # NOTE: Using environment.variables (not sessionVariables) because PAM pam_env
  # requires @{var} brace syntax, but @im=fcitx is a literal value.
  environment = {
    variables = {
      QT_IM_MODULE = "fcitx";
      XMODIFIERS = "@im=fcitx";
      SDL_IM_MODULE = "fcitx";
      INPUT_METHOD = "fcitx";
      GLFW_IM_MODULE = "ibus"; # GLFW fallback
    };

    systemPackages = with pkgs; [
      qt6Packages.fcitx5-with-addons
      libpinyin
    ];
  };
}
