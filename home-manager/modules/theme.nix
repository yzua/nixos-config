# Apply one Gruvbox Dark Soft palette and a coordinated font set to user apps.

{
  config,
  lib,
  pkgs,
  ...
}:

{
  stylix = {
    enable = true;
    # Keep targets tied to apps this profile actually uses.
    autoEnable = false;
    base16Scheme = "${pkgs.base16-schemes}/share/themes/gruvbox-dark-soft.yaml";
    polarity = "dark";

    fonts = {
      sansSerif = {
        package = pkgs.ibm-plex.override {
          families = [
            "sans"
            "sans-arabic"
          ];
        };
        name = "IBM Plex Sans";
      };
      serif = {
        package = pkgs.noto-fonts;
        name = "Noto Serif";
      };
      monospace = {
        package = pkgs.jetbrains-mono;
        name = "JetBrains Mono";
      };
      emoji = {
        package = pkgs.noto-fonts-color-emoji;
        name = "Noto Color Emoji";
      };
      sizes = {
        desktop = 12;
        applications = 13;
        terminal = 14;
        popups = 12;
      };
    };

    targets = {
      firefox.enable = true;
      font-packages.enable = true;
      fontconfig.enable = true;
      fzf.enable = true;
      ghostty.enable = true;
      gnome.enable = true;
      gtk.enable = true;
      mangohud.enable = true;
      nixcord.enable = true;
      starship.enable = true;
      tmux.enable = true;
      # VS Code already uses Gruvbox Dark Soft through its writable settings.json.
      vscode.enable = false;
    };
  };

  home.packages = [
    pkgs.amiri
    pkgs.nerd-fonts.symbols-only
    pkgs.noto-fonts-cjk-sans
    pkgs.noto-fonts-cjk-serif
  ];

  fonts.fontconfig = {
    enable = true;
    # Follow the selected Latin faces with script-specific glyph fallbacks.
    defaultFonts = {
      sansSerif = lib.mkAfter [
        "IBM Plex Sans Arabic"
        "Noto Sans CJK JP"
        "Noto Sans Symbols 2"
        "Noto Color Emoji"
      ];
      serif = lib.mkAfter [
        "Amiri"
        "Noto Serif CJK JP"
        "Noto Color Emoji"
      ];
      monospace = lib.mkAfter [
        "IBM Plex Sans Arabic"
        "Noto Sans Mono CJK JP"
        "Symbols Nerd Font Mono"
        "Noto Sans Symbols 2"
      ];
    };

    # Explicit font requests also need Arabic and symbol fallback before DejaVu.
    configFile.script-fallbacks = {
      enable = true;
      priority = 51;
      text = ''
        <?xml version="1.0"?>
        <!DOCTYPE fontconfig SYSTEM "fonts.dtd">
        <fontconfig>
          <alias binding="same">
            <family>IBM Plex Sans</family>
            <accept>
              <family>IBM Plex Sans Arabic</family>
              <family>Noto Sans CJK JP</family>
              <family>Noto Sans Symbols 2</family>
              <family>Noto Color Emoji</family>
            </accept>
          </alias>
          <alias binding="same">
            <family>Noto Serif</family>
            <accept>
              <family>Amiri</family>
              <family>Noto Serif CJK JP</family>
              <family>Noto Color Emoji</family>
            </accept>
          </alias>
          <alias binding="same">
            <family>JetBrains Mono</family>
            <accept>
              <family>IBM Plex Sans Arabic</family>
              <family>Noto Sans Mono CJK JP</family>
              <family>Symbols Nerd Font Mono</family>
              <family>Noto Sans Symbols 2</family>
            </accept>
          </alias>
          <alias binding="same">
            <family>JetBrainsMono Nerd Font</family>
            <accept>
              <family>JetBrains Mono</family>
              <family>Symbols Nerd Font</family>
            </accept>
          </alias>
        </fontconfig>
      '';
    };
  };

  # Use the same crisp pointer in Niri, GTK apps, and the GNOME fallback.
  home.pointerCursor = {
    package = pkgs.phinger-cursors;
    name = "phinger-cursors-light";
    size = 32;
    gtk.enable = true;
  };

  dconf.settings."org/gnome/desktop/interface" = {
    cursor-theme = config.home.pointerCursor.name;
    cursor-size = config.home.pointerCursor.size;
  };

  # GNOME only discovers a newly installed extension after the next login.
  # Stylix's immediate reload fails on the first activation in that case.
  xdg.dataFile."themes/Stylix/gnome-shell/gnome-shell.css".onChange = lib.mkForce ''
    extension=${lib.escapeShellArg pkgs.gnomeExtensions.user-themes.passthru.extensionUuid}
    if command -v gnome-extensions >/dev/null 2>&1 && gnome-extensions list | grep -Fxq "$extension"; then
      gnome-extensions disable "$extension" >/dev/null 2>&1 || true
      if ! gnome-extensions enable "$extension"; then
        echo "Stylix: GNOME will load User Themes at the next login" >&2
      fi
    else
      echo "Stylix: GNOME will load User Themes at the next login"
    fi
  '';
}
