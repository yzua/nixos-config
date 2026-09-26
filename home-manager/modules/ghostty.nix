# Ghostty terminal with on-demand GNOME integration and one Bash shell hook.

{
  programs.ghostty = {
    enable = true;
    # Ghostty injects integration into its initial Bash shell automatically.
    enableBashIntegration = false;
    # Install the user D-Bus/systemd units for on-demand windows, not login startup.
    systemd.enable = true;
  };
}
