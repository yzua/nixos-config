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
      font_family = config.stylix.fonts.sansSerif.name;
      polkit_agent = true;
      setup_wizard_enabled = false;
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
