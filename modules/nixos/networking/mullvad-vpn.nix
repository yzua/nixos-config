# Mullvad VPN daemon and GUI, without an automatic connection or setuid bypass.

{ pkgs, ... }:

{
  services.mullvad-vpn = {
    enable = true;
    # The default `mullvad` package has only the CLI, not the desktop GUI.
    package = pkgs.mullvad-vpn;
    enableExcludeWrapper = false;
  };
}
