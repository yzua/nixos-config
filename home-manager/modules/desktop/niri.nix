# Configure the Niri desktop, input layouts, shell startup, and window controls.

{
  aiPackages,
  config,
  lib,
  pkgs,
  setup,
  ...
}:

let
  colors = config.lib.stylix.colors.withHashtag;
  ghostty = lib.getExe pkgs.ghostty;
  noctalia = lib.getExe pkgs.noctalia;
  voiceAction = lib.getExe (import ../ai/voice/action.nix { inherit aiPackages pkgs; });
in
{
  xdg.configFile."niri/config.kdl".text = ''
    ${lib.optionalString (setup.monitor != null) ''
      output "${setup.monitor.match}" {
        mode "${setup.monitor.mode}"
      }
    ''}

    input {
      keyboard {
        xkb {
          layout "${lib.concatStringsSep "," setup.keyboard.layouts}"
          options "${setup.keyboard.toggle}"
        }
      }
    }

    cursor {
      xcursor-theme "${config.home.pointerCursor.name}"
      xcursor-size ${toString config.home.pointerCursor.size}
    }

    // Ask apps that support server decorations to omit their title bars.
    prefer-no-csd

    layout {
      background-color "transparent"
      struts {
        top -2
      }
      focus-ring {
        active-color "${colors.base0D}"
        inactive-color "${colors.base03}"
      }
    }

    animations {
      horizontal-view-movement {
        off
      }
    }

    // Keep Noctalia's wallpaper fixed behind Niri's scrolling workspaces.
    layer-rule {
      match namespace="^noctalia-wallpaper"
      place-within-backdrop true
    }

    window-rule {
      geometry-corner-radius 8
      clip-to-geometry true
    }

    window-rule {
      match app-id="dev.noctalia.Noctalia"
      open-floating true
    }

    // Keep the startup destinations available and ordered, even while empty.
    workspace "1"
    workspace "2"
    workspace "3"
    workspace "4"

    // Placement expires after Niri's first 60 seconds; windows remain movable.
    window-rule {
      match at-startup=true app-id=r#"(?i)^firefox$"#
      open-on-workspace "1"
    }

    window-rule {
      match at-startup=true app-id=r#"^com\.mitchellh\.ghostty$"#
      match at-startup=true app-id=r#"(?i)^code$"#
      open-on-workspace "2"
      open-focused false
    }

    window-rule {
      match at-startup=true app-id=r#"^(org\.telegram\.desktop|TelegramDesktop)$"#
      match at-startup=true app-id=r#"(?i)^vesktop$"#
      open-on-workspace "3"
      open-focused false
    }

    window-rule {
      match at-startup=true app-id=r#"^(Mullvad VPN|mullvad-vpn)$"#
      match at-startup=true app-id=r#"^NetBird$"#
      open-on-workspace "4"
      open-focused false
    }

    spawn-at-startup "${noctalia}"
    spawn-at-startup "${lib.getExe config.programs.firefox.package}"
    spawn-at-startup "${ghostty}"
    spawn-at-startup "${lib.getExe config.programs.vscode.package}"
    spawn-at-startup "${lib.getExe' pkgs.telegram-desktop "Telegram"}"
    spawn-at-startup "${lib.getExe config.programs.nixcord.vesktop.package}"
    // Launch the Mullvad GUI supplied by the active NixOS VPN service.
    spawn-at-startup "${lib.getExe' pkgs.glib "gio"}" "launch" "/run/current-system/sw/share/applications/mullvad-vpn.desktop"
    // Reuse NetBird's launcher, including its daemon-control group handling.
    spawn-at-startup "${lib.getExe' pkgs.glib "gio"}" "launch" "${config.home.profileDirectory}/share/applications/netbird.desktop"

    binds {
      Mod+Shift+Slash { show-hotkey-overlay; }

      Mod+Return { spawn "${ghostty}"; }
      Mod+Shift+Return { spawn "${ghostty}" "--gtk-single-instance=false" "--env=GHOSTTY_NO_TMUX=1"; }
      Mod+Space { spawn "${noctalia}" "msg" "panel-toggle" "launcher"; }
      Mod+V { spawn "${noctalia}" "msg" "panel-toggle" "clipboard"; }
      Mod+S { spawn "${noctalia}" "msg" "panel-toggle" "control-center"; }
      Mod+D repeat=false { spawn "${voiceAction}" "dictation-toggle"; }
      Mod+X repeat=false { spawn "${voiceAction}"; }
      Mod+Shift+X repeat=false { spawn "${voiceAction}" "reset"; }
      Mod+Shift+Escape repeat=false { spawn "${voiceAction}" "cancel"; }
      Mod+Shift+Comma { spawn "${noctalia}" "msg" "settings-toggle"; }
      Alt+Tab { spawn "${noctalia}" "msg" "window-switcher"; }
      Mod+Home { spawn "${noctalia}" "msg" "session" "lock"; }

      XF86AudioRaiseVolume { spawn "${noctalia}" "msg" "volume-up"; }
      XF86AudioLowerVolume { spawn "${noctalia}" "msg" "volume-down"; }
      XF86AudioMute repeat=false { spawn "${noctalia}" "msg" "volume-mute"; }
      XF86AudioMicMute repeat=false { spawn "${noctalia}" "msg" "mic-mute"; }
      XF86MonBrightnessUp { spawn "${noctalia}" "msg" "brightness-up"; }
      XF86MonBrightnessDown { spawn "${noctalia}" "msg" "brightness-down"; }
      XF86AudioPlay repeat=false { spawn "${noctalia}" "msg" "media" "toggle"; }
      XF86AudioStop repeat=false { spawn "${noctalia}" "msg" "media" "stop"; }
      XF86AudioPrev repeat=false { spawn "${noctalia}" "msg" "media" "previous"; }
      XF86AudioNext repeat=false { spawn "${noctalia}" "msg" "media" "next"; }

      Mod+O repeat=false { toggle-overview; }
      Mod+Q repeat=false { close-window; }

      Mod+Left { focus-column-left; }
      Mod+Down { focus-window-down; }
      Mod+Up { focus-window-up; }
      Mod+Right { focus-column-right; }
      Mod+H { focus-column-left; }
      Mod+J { focus-window-down; }
      Mod+K { focus-window-up; }
      Mod+L { focus-column-right; }

      Mod+Ctrl+Left { move-column-left; }
      Mod+Ctrl+Down { move-window-down; }
      Mod+Ctrl+Up { move-window-up; }
      Mod+Ctrl+Right { move-column-right; }
      Mod+Ctrl+H { move-column-left; }
      Mod+Ctrl+J { move-window-down; }
      Mod+Ctrl+K { move-window-up; }
      Mod+Ctrl+L { move-column-right; }

      Mod+Shift+Left { move-column-left; }
      Mod+Shift+Down { move-window-down; }
      Mod+Shift+Up { move-window-up; }
      Mod+Shift+Right { move-column-right; }
      Mod+Shift+H { move-column-left; }
      Mod+Shift+J { move-window-down; }
      Mod+Shift+K { move-window-up; }
      Mod+Shift+L { move-column-right; }

      Mod+Alt+Left { focus-monitor-left; }
      Mod+Alt+Down { focus-monitor-down; }
      Mod+Alt+Up { focus-monitor-up; }
      Mod+Alt+Right { focus-monitor-right; }
      Mod+Shift+Ctrl+Left { move-column-to-monitor-left; }
      Mod+Shift+Ctrl+Down { move-column-to-monitor-down; }
      Mod+Shift+Ctrl+Up { move-column-to-monitor-up; }
      Mod+Shift+Ctrl+Right { move-column-to-monitor-right; }

      Mod+Page_Down { focus-workspace-down; }
      Mod+Page_Up { focus-workspace-up; }
      Mod+U { focus-workspace-down; }
      Mod+I { focus-workspace-up; }
      Mod+Ctrl+Page_Down { move-column-to-workspace-down; }
      Mod+Ctrl+Page_Up { move-column-to-workspace-up; }
      Mod+Ctrl+U { move-column-to-workspace-down; }
      Mod+Ctrl+I { move-column-to-workspace-up; }

      Mod+1 { focus-workspace 1; }
      Mod+2 { focus-workspace 2; }
      Mod+3 { focus-workspace 3; }
      Mod+4 { focus-workspace 4; }
      Mod+5 { focus-workspace 5; }
      Mod+6 { focus-workspace 6; }
      Mod+7 { focus-workspace 7; }
      Mod+8 { focus-workspace 8; }
      Mod+9 { focus-workspace 9; }
      Mod+Shift+1 { move-window-to-workspace 1; }
      Mod+Shift+2 { move-window-to-workspace 2; }
      Mod+Shift+3 { move-window-to-workspace 3; }
      Mod+Shift+4 { move-window-to-workspace 4; }
      Mod+Shift+5 { move-window-to-workspace 5; }
      Mod+Shift+6 { move-window-to-workspace 6; }
      Mod+Shift+7 { move-window-to-workspace 7; }
      Mod+Shift+8 { move-window-to-workspace 8; }
      Mod+Shift+9 { move-window-to-workspace 9; }
      Mod+Ctrl+1 { move-column-to-workspace 1; }
      Mod+Ctrl+2 { move-column-to-workspace 2; }
      Mod+Ctrl+3 { move-column-to-workspace 3; }
      Mod+Ctrl+4 { move-column-to-workspace 4; }
      Mod+Ctrl+5 { move-column-to-workspace 5; }
      Mod+Ctrl+6 { move-column-to-workspace 6; }
      Mod+Ctrl+7 { move-column-to-workspace 7; }
      Mod+Ctrl+8 { move-column-to-workspace 8; }
      Mod+Ctrl+9 { move-column-to-workspace 9; }

      Mod+BracketLeft { consume-or-expel-window-left; }
      Mod+BracketRight { consume-or-expel-window-right; }
      Mod+Comma { consume-window-into-column; }
      Mod+Period { expel-window-from-column; }
      Mod+R { switch-preset-column-width; }
      Mod+Shift+R { switch-preset-column-width-back; }
      Mod+Ctrl+R { reset-window-height; }
      Mod+F { toggle-window-floating; }
      Mod+Shift+F { fullscreen-window; }
      Mod+M { maximize-window-to-edges; }
      Mod+Shift+M { maximize-column; }
      Mod+Ctrl+M { maximize-window-to-edges; }
      Mod+Ctrl+F { expand-column-to-available-width; }
      Mod+C { center-column; }
      Mod+Minus { set-column-width "-10%"; }
      Mod+Equal { set-column-width "+10%"; }
      Mod+Shift+Minus { set-window-height "-10%"; }
      Mod+Shift+Equal { set-window-height "+10%"; }
      Mod+Shift+V { switch-focus-between-floating-and-tiling; }
      Mod+W { toggle-column-tabbed-display; }

      Print { screenshot; }
      Ctrl+Print { screenshot-screen; }
      Alt+Print { screenshot-window; }
      Mod+Escape allow-inhibiting=false { toggle-keyboard-shortcuts-inhibit; }
      Mod+Shift+E { quit; }
      Ctrl+Alt+Delete { quit; }
      Mod+Shift+P { power-off-monitors; }
    }
  '';
}
