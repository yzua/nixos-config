# Install Noctalia and declare its stable shell preferences without owning runtime state.

{
  config,
  pkgs,
  ...
}:

let
  colors = config.lib.stylix.colors.withHashtag;
  toml = pkgs.formats.toml { };
in
{
  home.packages = [ pkgs.noctalia ];

  xdg.configFile."noctalia/config.toml".source = toml.generate "noctalia-config.toml" {
    backdrop.enabled = true;

    bar.default = {
      start = [
        "taskbar"
        "media"
      ];
      end = [
        "tray"
        "notifications"
        "clipboard"
        "network"
        "bluetooth"
        "volume"
        "brightness"
        "battery"
        "control-center"
        "session"
      ];
    };

    theme = {
      mode = "dark";
      source = "builtin";
      builtin = "Gruvbox";
      templates = {
        enable_builtin_templates = false;
        enable_community_templates = false;
        builtin_ids = [ ];
        community_ids = [ ];
      };
    };

    shell = {
      app_icon_colorize = true;
      font_family = config.stylix.fonts.sansSerif.name;
      niri_overview_type_to_launch_enabled = true;
      polkit_agent = true;
      screen_time_enabled = true;
      setup_wizard_enabled = false;
    };

    widget.workspaces = {
      capsule = true;
      hide_when_empty = true;
      label_source = "name";
      labels_only_when_occupied = true;
    };

    widget.taskbar = {
      type = "taskbar";
      group_by_workspace = true;
      group_single_icon_per_app = true;
      hide_empty_workspaces = false;
      icon_scale = 1.2;
      show_workspace_label = true;
      show_active_indicator = true;
    };

    wallpaper.default.path = "color:${colors.base00}";

    idle.behavior = {
      lock = {
        enabled = true;
        timeout = 600;
        action = "lock";
      };
      "screen-off" = {
        enabled = true;
        timeout = 900;
        action = "screen_off";
      };
    };
  };
}
