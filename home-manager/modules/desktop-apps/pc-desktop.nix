# One-click encrypted LAN desktop client; pairing remains private mutable state.

{ pkgs, setup, ... }:

let
  remote = setup.remoteDesktop;
  launcher = pkgs.writeShellApplication {
    name = "pc-desktop";
    runtimeInputs = [ pkgs.moonlight-qt ];
    text = ''
      # Qt creates identity keys here; protect both existing and new credentials.
      umask 077
      settings="''${XDG_CONFIG_HOME:-$HOME/.config}/Moonlight Game Streaming Project"
      mkdir -p "$settings"
      chmod 700 "$settings"
      if [[ -f "$settings/Moonlight.conf" ]]; then
        chmod 600 "$settings/Moonlight.conf"
      fi
      exec moonlight stream \
        --resolution ${remote.resolution} \
        --fps ${toString remote.fps} \
        --bitrate ${toString remote.bitrateKbps} \
        --video-codec H.264 \
        --video-decoder hardware \
        --no-hdr --no-yuv444 --audio-config stereo \
        --display-mode borderless \
        --capture-system-keys fullscreen \
        --absolute-mouse --no-game-optimization --no-quit-after \
        ${remote.hostAddress} ${pkgs.lib.escapeShellArg remote.appName} "$@"
    '';
  };
in
{
  home.packages = [
    pkgs.moonlight-qt
    launcher
  ];
  xdg.desktopEntries.pc-desktop = {
    name = "PC Desktop";
    comment = "View and control the configured desktop host over the LAN";
    exec = "${launcher}/bin/pc-desktop";
    icon = "moonlight";
    terminal = false;
    categories = [
      "Network"
      "RemoteAccess"
    ];
  };
}
