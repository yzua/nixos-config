# Keep Herdr's desktop preferences declarative without managing its sessions or integrations.

_:

{
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
