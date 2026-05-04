# Glance self-hosted dashboard with Gruvbox theme (localhost:8082).

{
  config,
  lib,
  pkgs,
  constants,
  user,
  ...
}:

let
  glanceSettings = import ./_settings.nix { inherit constants; };
  githubTokenService = import ./_github-token-service.nix { inherit lib pkgs user; };
in
{
  options.mySystem.glance = {
    enable = lib.mkEnableOption "Glance dashboard";
  };

  config = lib.mkIf config.mySystem.glance.enable {
    services.glance = {
      enable = true;
      openFirewall = false; # SECURITY: Localhost only
      environmentFile = "/run/glance/github-token.env";
      settings = glanceSettings;
    };

    systemd.services.glance = githubTokenService;
  };
}
