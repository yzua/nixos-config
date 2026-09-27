# Open NetBird's Quick Actions window from the desktop launcher.

{ pkgs, ... }:

{
  xdg.desktopEntries.netbird = {
    name = "NetBird";
    comment = "Manage the NetBird VPN connection";
    # The user manager can retain its old groups across a desktop logout.
    exec = ''/run/wrappers/bin/sg netbird -c "/run/current-system/sw/bin/netbird-ui --quick-actions=true"'';
    icon = "${pkgs.netbird-ui}/share/icons/hicolor/256x256/apps/netbird.png";
    categories = [ "Network" ];
    terminal = false;
  };
}
