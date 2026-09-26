# Configure Herdr preferences and provide the runtime for its Codex integration.

{ pkgs, ... }:

{
  # The bundled Codex SessionStart hook silently skips reporting without python3.
  home.packages = [ pkgs.python3 ];

  xdg.configFile."herdr/config.toml".text = ''
    onboarding = false

    [theme]
    name = "terminal"
    auto_switch = false

    [ui]
    status_indicators = "symbols"
    agent_panel_sort = "priority"

    [ui.toast]
    delivery = "system"
    delay_seconds = 1

    [update]
    version_check = false
  '';
}
