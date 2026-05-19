# RustDesk remote desktop client.

{
  config,
  lib,
  pkgs,
  ...
}:

{
  options.mySystem.rustdesk = {
    enable = lib.mkEnableOption "RustDesk remote desktop client";
  };

  config = lib.mkIf config.mySystem.rustdesk.enable {
    environment.systemPackages = [ pkgs.rustdesk ];
  };
}
