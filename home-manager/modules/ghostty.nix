# Ghostty terminal with on-demand GNOME integration and automatic shell hooks.

{
  programs.ghostty = {
    enable = true;
    # Ghostty injects integration into its initial Bash or Zsh shell itself.
    enableBashIntegration = false;
    enableZshIntegration = false;
    # Keep prompt/CWD integration without Ghostty's command-text titles.
    settings."shell-integration-features" = "no-title";
    # Install the user D-Bus/systemd units for on-demand windows, not login startup.
    systemd.enable = true;
  };
}
