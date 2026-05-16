# Custom utility scripts added to user PATH.

{
  config,
  constants,
  pkgs,
  ...
}:

let
  scriptsDir = "${config.home.homeDirectory}/${constants.paths.scripts}";
  zellijWebPort = toString constants.ports.zellij-web;
  zellijWebPasswordFile = "/run/secrets/zellij_web_password";
in
{
  home.packages = with pkgs; [
    (writeShellScriptBin "nvidia-fans" ''
      exec ${scriptsDir}/hardware/nvidia-fans.sh "$@"
    '')
    (writeShellScriptBin "zellij-main" ''
            set -euo pipefail

            for layout_path in "$HOME"/.cache/zellij/*/session_info/main/session-layout.kdl; do
              [[ -e "$layout_path" ]] || continue

              if ! ${pkgs.python3}/bin/python3 - "$layout_path" <<'PY'
      import pathlib
      import sys

      path = pathlib.Path(sys.argv[1])
      data = path.read_bytes()

      if not data:
          raise SystemExit(1)
      if b"\x00" in data:
          raise SystemExit(1)

      try:
          text = data.decode("utf-8")
      except UnicodeDecodeError:
          raise SystemExit(1)

      if "layout" not in text:
          raise SystemExit(1)
      PY
              then
                rm -rf "$(dirname "$layout_path")"
              fi
            done

            exec ${pkgs.zellij}/bin/zellij attach --create main "$@"
    '')
    (writeShellScriptBin "zellij-mobile" ''
      exec ${pkgs.zellij}/bin/zellij attach --create mobile --layout "$HOME/.config/zellij/layouts/mobile-ai.kdl" "$@"
    '')
    (writeShellScriptBin "zellij-web-password" ''
      set -euo pipefail
      password_file=${zellijWebPasswordFile}

      if [[ ! -r "$password_file" ]]; then
        echo "Missing Zellij Web login token secret: $password_file" >&2
        echo "Add zellij_web_password to secrets/secrets.yaml with just secrets-add or just sops-edit." >&2
        exit 1
      fi

      cat "$password_file"
    '')
    (writeShellScriptBin "zellij-web-token" ''
      exec ${pkgs.zellij}/bin/zellij web --create-token
    '')
    (writeShellScriptBin "zellij-web-status" ''
      exec ${pkgs.zellij}/bin/zellij web --port ${zellijWebPort} --status --timeout 2
    '')
    (writeShellScriptBin "zphone" ''
      set -euo pipefail

      zellij="${pkgs.zellij}/bin/zellij"
      tailscale="${pkgs.tailscale}/bin/tailscale"
      mobile_session="mobile"
      mobile_layout="$HOME/.config/zellij/layouts/mobile-ai.kdl"
      mobile_url_base=""
      password=""

      systemctl --user start zellij-web.service >/dev/null 2>&1 || true

      "$zellij" attach --forget --create-background "$mobile_session"
      "$zellij" -s "$mobile_session" action override-layout --apply-only-to-active-tab "$mobile_layout"
      "$zellij" -s "$mobile_session" action save-session

      for _ in $(seq 1 20); do
        if "$zellij" web --port ${zellijWebPort} --status --timeout 2 >/dev/null 2>&1; then
          break
        fi
        sleep 1
      done

      if ! "$tailscale" serve status >/dev/null 2>&1; then
        sudo "$tailscale" serve --bg --https=443 http://127.0.0.1:${zellijWebPort}
      fi

      mobile_url_base="$("$tailscale" serve status 2>/dev/null | awk 'match($0, /^https:\/\/[^ ]+/) { print substr($0, RSTART, RLENGTH); exit }')"
      if [[ -z "$mobile_url_base" ]]; then
        echo "Could not read Tailscale Serve URL." >&2
        exit 1
      fi

      if [[ ! -r ${zellijWebPasswordFile} ]]; then
        echo "Missing Zellij Web login token secret: ${zellijWebPasswordFile}" >&2
        echo "Run just secrets-add zellij_web_password, then just nixos and just home." >&2
        exit 1
      fi

      password="$(cat ${zellijWebPasswordFile})"
      if [[ -z "$password" ]]; then
        echo "Zellij Web password secret is empty." >&2
        exit 1
      fi

      printf '%s\n' \
        "Phone URL: ''${mobile_url_base%/}/$mobile_session" \
        "Login token: $password" \
        "Session: $mobile_session" \
        "Next: open the URL on iPhone and paste the login token."
    '')
  ];
}
