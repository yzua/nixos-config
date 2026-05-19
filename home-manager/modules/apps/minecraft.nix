# Waylandcraft Fabric instance seed for PrismLauncher / FjordLauncher.

{
  config,
  lib,
  pkgs,
  ...
}:

let
  minecraftVersion = "26.1.2";
  fabricLoaderVersion = "0.19.2";
  fabricApiVersion = "0.147.0+26.1.2";
  waylandcraftVersion = "1.0.0";
  wrapperPath = "${config.home.homeDirectory}/.local/share/PrismLauncher/minecraft-wayland-wrap.sh";
  runtimeLibraryPath = lib.makeLibraryPath [
    pkgs.libglvnd
    pkgs.libdecor
    pkgs.libxkbcommon
    pkgs.wayland
  ];

  waylandcraftJar = pkgs.fetchurl {
    url = "https://github.com/EVV1E/waylandcraft/releases/download/v${waylandcraftVersion}/waylandcraft-${waylandcraftVersion}.jar";
    hash = "sha256-0jri+768fvjynuxnlcCI0Uql0HIy9E4IOUDDNjKOxlM=";
  };

  fabricApiJar = pkgs.fetchurl {
    url = "https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/${fabricApiVersion}/fabric-api-${fabricApiVersion}.jar";
    hash = "sha256-q3h3qPfI5HVw0+txBLL7LzoyT21lU1b+c5Z/LTKQurg=";
  };
in
{
  home.file.".local/share/PrismLauncher/minecraft-wayland-wrap.sh" = {
    executable = true;
    text = ''
      #!${pkgs.bash}/bin/bash
      set -euo pipefail

      render_node="''${WAYLANDCRAFT_RENDER_NODE:-/dev/dri/renderD128}"
      log_file="$HOME/.local/share/PrismLauncher/gamescope-waylandcraft.log"
      gamescope_bin="/run/wrappers/bin/gamescope"

      if [[ ! -x "$gamescope_bin" ]]; then
        gamescope_bin="${pkgs.gamescope}/bin/gamescope"
      fi

      export LD_LIBRARY_PATH="${runtimeLibraryPath}:''${LD_LIBRARY_PATH:-}"

      unset GBM_BACKEND
      unset LIBGL_ALWAYS_SOFTWARE
      unset MESA_LOADER_DRIVER_OVERRIDE
      unset GALLIUM_DRIVER

      focus_gamescope_window() {
        local socket="''${NIRI_SOCKET:-}"

        if [[ -z "$socket" ]]; then
          for candidate in "''${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"/niri.*.sock; do
            [[ -S "$candidate" ]] || continue
            socket="$candidate"
            break
          done
        fi

        [[ -n "$socket" ]] || return 0

        local window_id=""
        local line=""
        for _ in {1..60}; do
          while IFS= read -r line; do
            if [[ "$line" =~ ^Window\ ID\ ([0-9]+): ]]; then
              window_id="''${BASH_REMATCH[1]}"
            elif [[ "$line" == *'App ID: "gamescope"'* ]] && [[ -n "$window_id" ]]; then
              NIRI_SOCKET="$socket" ${pkgs.niri}/bin/niri msg action move-window-to-monitor --id "$window_id" HDMI-A-1 >/dev/null 2>&1 || true
              NIRI_SOCKET="$socket" ${pkgs.niri}/bin/niri msg action focus-window --id "$window_id" >/dev/null 2>&1 || true
              NIRI_SOCKET="$socket" ${pkgs.niri}/bin/niri msg action fullscreen-window >/dev/null 2>&1 || true
              return 0
            fi
          done < <(NIRI_SOCKET="$socket" ${pkgs.niri}/bin/niri msg windows 2>/dev/null || true)

          sleep 0.25
        done
      }

      focus_gamescope_window </dev/null >/dev/null 2>&1 &

      exec env SDL_VIDEODRIVER=wayland "$gamescope_bin" \
        --backend wayland \
        --prefer-vk-device 10de:1f07 \
        -W 2560 \
        -H 1080 \
        -w 2560 \
        -h 1080 \
        -r 75 \
        -S stretch \
        --force-composition \
        --disable-layers \
        --force-grab-cursor \
        -- \
        env \
          -u WAYLAND_DISPLAY \
          WAYLANDCRAFT_RENDER_NODE="$render_node" \
          WAYLANDCRAFT_DISABLE_DMABUF="1" \
          LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
          __GLX_VENDOR_LIBRARY_NAME="nvidia" \
          XDG_SESSION_TYPE="x11" \
          "$@" 2>>"$log_file"
    '';
  };

  home.activation.seedWaylandcraftPrismInstance = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
        instance_dir="$HOME/.local/share/PrismLauncher/instances/Waylandcraft"
        mods_dir="$instance_dir/.minecraft/mods"
        local_waylandcraft_jar="$HOME/Documents/waylandcraft/build/libs/waylandcraft-${waylandcraftVersion}.jar"

        mkdir -p "$mods_dir"

        set_or_append_ini_key() {
          local file="$1"
          local key="$2"
          local value="$3"
          local line="''${key}=''${value}"
          local tmp
          local existing
          local replaced=0

          tmp="$(mktemp)"

          while IFS= read -r existing || [ -n "$existing" ]; do
            if [[ "$existing" == "''${key}="* ]]; then
              printf '%s\n' "$line" >> "$tmp"
              replaced=1
            else
              printf '%s\n' "$existing" >> "$tmp"
            fi
          done < "$file"

          if [[ "$replaced" -eq 0 ]]; then
            printf '%s\n' "$line" >> "$tmp"
          fi

          mv "$tmp" "$file"
        }

        if [ ! -e "$instance_dir/instance.cfg" ]; then
          cat > "$instance_dir/instance.cfg" <<'EOF'
    ConfigVersion=1.2
    InstanceType=OneSix
    iconKey=fabric
    name=Waylandcraft
    EOF
        fi

        set_or_append_ini_key "$instance_dir/instance.cfg" "Env" "{WAYLANDCRAFT_RENDER_NODE:/dev/dri/renderD128,WAYLANDCRAFT_DISABLE_DMABUF:1}"
        set_or_append_ini_key "$instance_dir/instance.cfg" "JvmArgs" "-DMC_DEBUG_ENABLED=true -Dwaylandcraft.disableEglBackend=true"
        set_or_append_ini_key "$instance_dir/instance.cfg" "OverrideCommands" "true"
        set_or_append_ini_key "$instance_dir/instance.cfg" "OverrideEnv" "true"
        set_or_append_ini_key "$instance_dir/instance.cfg" "OverrideJavaArgs" "true"
        set_or_append_ini_key "$instance_dir/instance.cfg" "OverrideNativeWorkarounds" "false"
        set_or_append_ini_key "$instance_dir/instance.cfg" "OverrideWindow" "true"
        set_or_append_ini_key "$instance_dir/instance.cfg" "MinecraftWinWidth" "2560"
        set_or_append_ini_key "$instance_dir/instance.cfg" "MinecraftWinHeight" "1080"
        set_or_append_ini_key "$instance_dir/instance.cfg" "UseNativeGLFW" "false"
        set_or_append_ini_key "$instance_dir/instance.cfg" "WrapperCommand" "${wrapperPath}"

        if [ ! -e "$instance_dir/mmc-pack.json" ]; then
          cat > "$instance_dir/mmc-pack.json" <<'EOF'
    {
      "components": [
        {
          "cachedName": "Minecraft",
          "important": true,
          "uid": "net.minecraft",
          "version": "${minecraftVersion}"
        },
        {
          "cachedName": "Fabric Loader",
          "uid": "net.fabricmc.fabric-loader",
          "version": "${fabricLoaderVersion}"
        }
      ],
      "formatVersion": 1
    }
    EOF
        fi

        if [ -e "$local_waylandcraft_jar" ]; then
          install -m 0644 "$local_waylandcraft_jar" "$mods_dir/waylandcraft-${waylandcraftVersion}.jar"
        else
          install -m 0644 ${waylandcraftJar} "$mods_dir/waylandcraft-${waylandcraftVersion}.jar"
        fi
        install -m 0644 ${fabricApiJar} "$mods_dir/fabric-api-${fabricApiVersion}.jar"
  '';
}
