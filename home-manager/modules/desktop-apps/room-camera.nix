# On-demand Room Cam viewing, person alerts, and a hand-motion data playground.

{ config, pkgs, ... }:

let
  camera = import ../../../packages/room-camera { inherit pkgs; };
  handTerminal = pkgs.writeShellApplication {
    name = "room-hand-tracker";
    text = ''
      exec ${config.programs.ghostty.package}/bin/ghostty --title="Room Hand Tracker" \
        -e ${camera}/bin/room-cam --hands "$@"
    '';
  };
in
{
  home.packages = [
    camera
    handTerminal
  ];
  xdg.desktopEntries.room-cam = {
    name = "Room Cam";
    comment = "Full-resolution local live view; no recording or streaming";
    exec = "${camera}/bin/room-cam";
    icon = "camera-video";
    terminal = false;
    categories = [ "AudioVideo" ];
  };
  xdg.desktopEntries.room-person-monitor = {
    name = "Room Person Monitor";
    comment = "Local person detection with desktop notifications; no recording";
    exec = "${camera}/bin/room-cam --monitor";
    icon = "camera-video";
    terminal = false;
    categories = [ "AudioVideo" ];
  };
  xdg.desktopEntries.room-hand-tracker = {
    name = "Room Hand Tracker";
    comment = "Live hand skeleton and terminal motion/gesture data; no control actions";
    exec = "${handTerminal}/bin/room-hand-tracker";
    icon = "camera-video";
    terminal = false;
    categories = [ "AudioVideo" ];
  };
}
