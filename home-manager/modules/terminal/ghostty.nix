# Ghostty terminal with on-demand GNOME integration and automatic shell hooks.

{ lib, ... }:

{
  programs.ghostty = {
    enable = true;
    # Ghostty injects integration into its initial Bash or Zsh shell itself.
    enableBashIntegration = false;
    enableZshIntegration = false;
    # Keep prompt/CWD integration without Ghostty's command-text titles.
    settings = {
      "shell-integration-features" = "no-title";
      # Keep Ghostty free of GTK window chrome and visible tabs.
      "window-decoration" = "none";
      "gtk-tabs-location" = "hidden";
      # Copy terminal selections to both the primary and regular clipboard.
      "copy-on-select" = "clipboard";
      "mouse-scroll-multiplier" = "precision:0.75,discrete:1";
      # Pass Alt+digits to tmux windows; Ghostty tabs still use Ctrl+Shift keys.
      keybind = lib.concatMap (
        n:
        let
          digit = toString n;
        in
        [
          "alt+${digit}=unbind"
          "alt+digit_${digit}=unbind"
        ]
      ) (lib.range 1 9);
    };
    # Install the user D-Bus/systemd units for on-demand windows, not login startup.
    systemd.enable = true;
  };
}
