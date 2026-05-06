# VNC remote access (x11vnc, noVNC, websockify).
# SECURITY: x11vnc defaults to NO encryption. Always tunnel through SSH or use
# the vnc-secure-startup launcher which forces localhost-only + SSH tunnel instructions.

{
  config,
  lib,
  pkgsStable,
  user,
  constants,
  ...
}:

let
  cfg = config.mySystem.vnc;

  vncSecureStartup = pkgsStable.writeShellScriptBin "vnc-secure-startup" ''
    set -euo pipefail

    password_file="$HOME/.vnc/passwd"
    if [[ ! -f "$password_file" ]]; then
      echo "Missing VNC password: $password_file" >&2
      echo "Create one with: x11vnc -storepasswd $password_file" >&2
      exit 1
    fi

    exec ${pkgsStable.x11vnc}/bin/x11vnc \
      -display "''${DISPLAY:-:0}" \
      -localhost \
      -rfbport ${toString constants.ports.vnc} \
      -rfbauth "$password_file" \
      -xkb \
      -forever \
      -shared
  '';
in
{
  options.mySystem.vnc = {
    enable = lib.mkEnableOption "VNC remote access with x11vnc, noVNC, and websockify";
    tools.enable = lib.mkEnableOption "localhost-only VNC launcher without enabling remote access by default";
  };

  config = lib.mkIf (cfg.enable || cfg.tools.enable) {
    environment.systemPackages = with pkgsStable; [
      x11vnc
      novnc
      python3Packages.websockify
      xclip # X11 clipboard access (useful for VNC sessions)
      vncSecureStartup
    ];

    # Security wrapper: VNC only accessible via SSH tunnel
    environment.etc."vnc-security-readme.txt".text = ''
      VNC SECURITY INSTRUCTIONS
      =========================
      x11vnc transmits data UNENCRYPTED. Never expose it directly to the network.

      CORRECT USAGE (SSH tunnel):
        1. Generate a VNC password (first time only):
           x11vnc -storepasswd ~/.vnc/passwd

        2. Start x11vnc on this host (localhost only):
           vnc-secure-startup

        3. From remote machine, create SSH tunnel:
           ssh -L ${toString constants.ports.vnc}:localhost:${toString constants.ports.vnc} ${user}@<this-host-ip>

        4. Connect VNC viewer to localhost:${toString constants.ports.vnc}

      noVNC WEB ACCESS (localhost only):
        websockify --web=${pkgsStable.novnc}/share/novnc ${toString constants.ports.vnc-web} localhost:${toString constants.ports.vnc}
        Then open http://localhost:${toString constants.ports.vnc-web}/vnc.html

      ALWAYS use -rfbauth with a stored password. NEVER expose port ${toString constants.ports.vnc}/${toString constants.ports.vnc-web} to the internet.
    '';

    # Firewall: Block VNC ports from external access (SSH tunnel only)
    networking.firewall.extraCommands = lib.mkIf cfg.enable ''
      # Block external VNC access — must use SSH tunnel
      iptables -A INPUT -p tcp --dport ${toString constants.ports.vnc} -s ${constants.localhost} -j ACCEPT
      iptables -A INPUT -p tcp --dport ${toString constants.ports.vnc} -j DROP
      iptables -A INPUT -p tcp --dport ${toString constants.ports.vnc-web} -s ${constants.localhost} -j ACCEPT
      iptables -A INPUT -p tcp --dport ${toString constants.ports.vnc-web} -j DROP
    '';
  };
}
