# Add a Niri session and on-demand X11 compatibility alongside GNOME.

{ pkgs, ... }:

{
  programs.niri.enable = true;

  # Niri finds this on PATH and starts it when an X11 client connects.
  environment.systemPackages = [ pkgs.xwayland-satellite ];
}
