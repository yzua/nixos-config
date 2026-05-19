# Automatic metadata scrubbing for user files.
# Watches Downloads and Desktop for new files and strips metadata using mat2/exiftool.
# Full scrub of Documents/Pictures runs weekly via timer.
# System packages (mat2/exiftool/inotify-tools) are provided by the NixOS module
# at nixos-modules/security/metadata-scrubber.nix.

{
  hmSystemdHelpers,
  lib,
  pkgs,
  pkgsStable,
  ...
}:

let
  inherit (hmSystemdHelpers) mkHmTimer;

  scrubberBinPath = lib.makeBinPath [
    pkgsStable.coreutils
    pkgsStable.mat2
    pkgsStable.exiftool
    pkgsStable.inotify-tools
  ];
in
{
  systemd.user = {
    services.metadata-scrubber = {
      Unit = {
        Description = "Automatic metadata scrubbing for new files";
        After = [ "graphical-session.target" ];
      };
      Service = {
        Type = "simple";
        ExecStart = pkgs.writeShellScript "metadata-scrubber" ''
          export PATH="${scrubberBinPath}:$PATH"
          WATCH_DIRS=(
            "$HOME/Downloads"
            "$HOME/Desktop"
          )

          # Create dirs if they don't exist
          for dir in "''${WATCH_DIRS[@]}"; do
            mkdir -p "$dir"
          done

          SCRUB_LOG="''${XDG_STATE_HOME:-$HOME/.local/state}/metadata-scrubber.log"
          mkdir -p "$(dirname "$SCRUB_LOG")"

          strip_metadata() {
            local file="$1"

            # Skip if file doesn't exist, is a directory, or a symlink
            [[ ! -f "$file" || -L "$file" ]] && return 0

            # Skip hidden files
            [[ "$(basename "$file")" == .* ]] && return 0

            # Skip common non-metadata-bearing formats
            local ext="''${file##*.}"
            ext="$(echo "$ext" | tr '[:upper:]' '[:lower:]')"

            case "$ext" in
              # Skip text/code/config files
              txt|md|nix|json|yaml|yml|toml|xml|html|css|js|ts|py|rs|go|c|h|cpp|sh|bash|zsh)
                return 0
                ;;
              # Skip archives
              zip|tar|gz|bz2|xz|7z|rar)
                return 0
                ;;
            esac

            # Use mat2 for comprehensive metadata removal
            if mat2 --inplace "$file" 2>/dev/null; then
              echo "$(date -Iseconds) | SCRUBBED(mat2) | $file" >> "$SCRUB_LOG"
            else
              # Fallback to exiftool for formats mat2 doesn't handle
              if exiftool -all= -overwrite_original "$file" 2>/dev/null; then
                echo "$(date -Iseconds) | SCRUBBED(exiftool) | $file" >> "$SCRUB_LOG"
              fi
            fi
          }

          echo "$(date -Iseconds) | STARTED | Watching: ''${WATCH_DIRS[*]}" >> "$SCRUB_LOG"

          inotifywait -m --format '%w%f' "''${WATCH_DIRS[@]}" | \
          while read -r file; do
            # Small delay to ensure file is fully written
            sleep 0.5
            strip_metadata "$file"
          done
        '';
        Restart = "on-failure";
        RestartSec = 10;
        PrivateTmp = true;
        NoNewPrivileges = true;
        MemoryMax = "128M";
        CPUQuota = "10%";
      };
      Install.WantedBy = [ "default.target" ];
    };

    services.metadata-scrubber-full = {
      Unit.Description = "Full metadata scrub of all user files";
      Service = {
        Type = "oneshot";
        ExecStart = pkgs.writeShellScript "metadata-scrubber-full" ''
          export PATH="${
            lib.makeBinPath [
              pkgsStable.mat2
              pkgsStable.exiftool
            ]
          }:$PATH"
          SCRUB_LOG="''${XDG_STATE_HOME:-$HOME/.local/state}/metadata-scrubber.log"
          mkdir -p "$(dirname "$SCRUB_LOG")"
          echo "$(date -Iseconds) | FULL_SCRUB_START" >> "$SCRUB_LOG"

          count=0
          for dir in "$HOME/Downloads" "$HOME/Desktop" "$HOME/Documents" "$HOME/Pictures"; do
            [[ -d "$dir" ]] || continue
            while IFS= read -r -d ''$'\0' file; do
              if mat2 --inplace "$file" 2>/dev/null; then
                count=$((count + 1))
              elif exiftool -all= -overwrite_original "$file" 2>/dev/null; then
                count=$((count + 1))
              fi
            done < <(find "$dir" -maxdepth 3 -type f ! -name '.*' -print0 2>/dev/null)
          done

          echo "$(date -Iseconds) | FULL_SCRUB_DONE | files_scrubbed=$count" >> "$SCRUB_LOG"
        '';
        PrivateTmp = true;
        NoNewPrivileges = true;
        MemoryMax = "512M";
      };
    };

    timers.metadata-scrubber-full = mkHmTimer {
      description = "Weekly full metadata scrub";
      onCalendar = "weekly";
      randomizedDelaySec = "2h";
      unit = "metadata-scrubber-full.service";
    };
  };
}
