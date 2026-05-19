# KDE Connect for phone-desktop integration.

{
  config,
  lib,
  ...
}:

{
  options.mySystem.kdeconnect = {
    enable = lib.mkEnableOption "KDE Connect phone-desktop integration";
  };

  config = lib.mkIf config.mySystem.kdeconnect.enable {
    # Opens firewall ports 1714-1764 TCP+UDP automatically
    programs.kdeconnect.enable = true;

    mySystem.mullvadVpn.lanServices = [ "kdeconnect" ];
  };
}
