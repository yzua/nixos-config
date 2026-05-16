# Ghostty terminal emulator configuration.

{
  constants,
  lib,
  pkgs,
  ...
}:

{
  programs.ghostty = {
    enable = true;
    package = pkgs.ghostty;

    enableZshIntegration = true;
    enableBashIntegration = true;

    settings = {
      font-family = constants.font.monoNerd;
      font-family-bold = constants.font.monoNerd;
      font-family-italic = constants.font.monoNerd;
      font-family-bold-italic = constants.font.monoNerd;
      font-size = lib.mkForce constants.font.size;
      font-thicken = true;
      adjust-cell-height = "0%";
      font-shaping-break = "cursor";

      # theme is managed by Stylix (stylix.targets.ghostty.enable = true)

      window-padding-x = 8;
      window-padding-y = 8;
      window-padding-balance = true;
      window-padding-color = "extend";
      window-decoration = false; # Niri handles decorations
      window-title-font-family = constants.font.monoNerd;
      window-theme = "dark";
      window-subtitle = "working-directory";
      window-inherit-working-directory = true;
      tab-inherit-working-directory = true;
      split-inherit-working-directory = true;
      window-new-tab-position = "current";
      window-show-tab-bar = "never";
      gtk-single-instance = true;

      cursor-style = "block";
      cursor-style-blink = true;
      cursor-color = constants.color.yellow_dim;
      cursor-click-to-move = true;

      copy-on-select = "clipboard";
      selection-invert-fg-bg = true;
      selection-clear-on-copy = true;
      clipboard-read = "allow";
      clipboard-write = "allow";
      clipboard-paste-protection = true;
      clipboard-trim-trailing-spaces = true;

      mouse-hide-while-typing = true;
      mouse-scroll-multiplier = "precision:1,discrete:3";
      focus-follows-mouse = true;
      mouse-shift-capture = "never";

      scrollback-limit = 50000000;
      scrollbar = "never";

      link-url = true;
      link-previews = true;

      shell-integration = "zsh";
      shell-integration-features = "cursor,sudo,title";

      bold-is-bright = false;
      unfocused-split-opacity = 0.82;
      unfocused-split-fill = constants.color.bg_hard;
      split-divider-color = constants.color.outline;
      split-preserve-zoom = "navigation";
      resize-overlay = "after-first";
      resize-overlay-position = "top-right";
      resize-overlay-duration = "600ms";
      gtk-tabs-location = "hidden"; # Zellij handles multiplexing

      notify-on-command-finish = "unfocused";
      notify-on-command-finish-action = "bell,notify";
      notify-on-command-finish-after = "20s";

      keybind = [
        "ctrl+shift+c=copy_to_clipboard"
        "ctrl+shift+v=paste_from_clipboard"
        "ctrl+plus=increase_font_size:1"
        "ctrl+minus=decrease_font_size:1"
        "ctrl+0=reset_font_size"
        "shift+page_up=scroll_page_up"
        "shift+page_down=scroll_page_down"
        "shift+home=scroll_to_top"
        "shift+end=scroll_to_bottom"
        "ctrl+shift+f=start_search"
        "escape=end_search"
        "ctrl+shift+u=copy_url_to_clipboard"
        "ctrl+shift+r=reload_config"
        "ctrl+shift+n=new_window"
        "ctrl+shift+t=new_tab"
        "ctrl+shift+w=close_surface"
        "ctrl+shift+o=new_split:right"
        "ctrl+shift+e=new_split:down"
        "ctrl+alt+h=goto_split:left"
        "ctrl+alt+j=goto_split:down"
        "ctrl+alt+k=goto_split:up"
        "ctrl+alt+l=goto_split:right"
        "ctrl+shift+z=toggle_split_zoom"
        "ctrl+l=text:\\x0c"
        "ctrl+shift+i=inspector:toggle"
        "ctrl+shift+p=toggle_command_palette"
      ];

      confirm-close-surface = false;
      auto-update = "off"; # Managed by Nix
    };
  };
}
