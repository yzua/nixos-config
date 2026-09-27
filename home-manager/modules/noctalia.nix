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
      border_width = 1.5;
      padding = 18;
      widget_spacing = 10;
      start = [
        "taskbar"
        "media"
      ];
      center = [
        "clock"
        "group:system"
      ];
      capsule_group = [
        {
          id = "system";
          members = [
            "cpu_usage"
            "cpu_temp"
            "gpu_usage"
            "gpu_temp"
            "gpu_vram"
            "ram_pct"
            "disk_used_pct"
          ];
          fill = "surface_variant";
          opacity = 0.65;
          padding = 3.0;
          widget_spacing = 2;
        }
      ];
      end = [
        "tray"
        "notifications"
        "network"
        "bluetooth"
        "volume"
        "brightness"
        "battery"
        "control-center"
        "session"
      ];
      thickness = 42;
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
      group_single_icon_per_app = false;
      hide_empty_workspaces = false;
      icon_scale = 1.2;
      minimal = true;
      show_workspace_label = true;
      show_active_indicator = true;
      workspace_label_placement = "inside";
    };

    widget.clock.format = "{:%-I:%M %p}";

    widget.cpu_usage = {
      type = "sysmon";
      stat = "cpu_usage";
      visualization = "none";
    };
    widget.cpu_temp = {
      type = "sysmon";
      stat = "cpu_temp";
      visualization = "none";
    };
    widget.gpu_usage = {
      type = "sysmon";
      stat = "gpu_usage";
      visualization = "none";
    };
    widget.gpu_temp = {
      type = "sysmon";
      stat = "gpu_temp";
      visualization = "none";
    };
    widget.gpu_vram = {
      type = "sysmon";
      stat = "gpu_vram";
      visualization = "none";
    };
    widget.ram_pct = {
      type = "sysmon";
      stat = "ram_pct";
      visualization = "none";
    };
    widget.disk_used_pct = {
      type = "sysmon";
      stat = "disk_used_pct";
      path = "/";
      visualization = "none";
    };
    widget.tray.match_adjacent_spacing = true;

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
