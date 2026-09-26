# Apply one Gruvbox Dark Soft palette and a coordinated font set to user apps.

{ lib, pkgs, ... }:

{
  stylix = {
    enable = true;
    # Keep targets tied to apps this profile actually uses.
    autoEnable = false;
    base16Scheme = "${pkgs.base16-schemes}/share/themes/gruvbox-dark-soft.yaml";
    polarity = "dark";

    fonts = {
      sansSerif = {
        package = pkgs.inter;
        name = "Inter";
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
        desktop = 11;
        applications = 12;
        terminal = 13;
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

  fonts.fontconfig.enable = true;

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
