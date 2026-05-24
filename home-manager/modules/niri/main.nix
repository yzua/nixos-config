# Main Niri compositor settings.

{
  config,
  constants,
  pkgs,
  ...
}:

let
  ws = import ./_workspace-names.nix;
  mainOutput = "HDMI-A-1";
  mkSpring =
    {
      dampingRatio,
      stiffness,
      epsilon,
    }:
    {
      damping-ratio = dampingRatio;
      inherit stiffness epsilon;
    };
  mkBackdropRule = namespace: {
    matches = [ { inherit namespace; } ];
    place-within-backdrop = true;
  };
in

{
  programs.niri.settings = {
    prefer-no-csd = true;
    hotkey-overlay.skip-at-startup = true;
    screenshot-path = "~/Screens/screenshot-%Y-%m-%d-%H-%M-%S.png";

    outputs = {
      "HDMI-A-1" = {
        mode = {
          width = 2560;
          height = 1080;
          refresh = 74.991;
        };
        position = {
          x = 1080;
          y = 420;
        };
        scale = 1;
        focus-at-startup = true;
      };

      "Samsung Electric Company C24FG70 HTHJ200179" = {
        mode = {
          width = 1920;
          height = 1080;
          refresh = 144.0;
        };
        transform.rotation = 90;
        position = {
          x = 0;
          y = 0;
        };
        scale = 1;
      };
    };

    workspaces = {
      "01-browser" = {
        name = ws.browser; # nf-md-web
        open-on-output = mainOutput;
      };
      "02-code" = {
        name = ws.editor; # nf-md-code-braces
        open-on-output = mainOutput;
      };
      "03-social" = {
        name = ws.social; # nf-md-chat
        open-on-output = mainOutput;
      };
      "04-media" = {
        name = ws.media; # nf-md-music
        open-on-output = mainOutput;
      };
      "05-vpn" = {
        name = ws.vpn; # nf-md-shield-lock
        open-on-output = mainOutput;
      };
      "06-android" = {
        name = ws.android; # nf-md-android
        open-on-output = mainOutput;
      };
      "07-web-re" = {
        name = ws.web-re;
        open-on-output = mainOutput;
      };
    };

    environment = {
      ELECTRON_OZONE_PLATFORM_HINT = "auto";
      # Prevent Electron/Chromium GPU sandbox contention with niri under load
      ELECTRON_EXTRA_LAUNCH_FLAGS = "--disable-gpu-sandbox";
      # QT_QPA_PLATFORM is set globally in home.nix sessionVariables
      QT_STYLE_OVERRIDE = "kvantum";
      XDG_SCREENSHOTS_DIR = "$HOME/Screens";
      SSH_AUTH_SOCK = "$XDG_RUNTIME_DIR/keepassxc-ssh-agent.socket";
    };

    spawn-at-startup = [
      { argv = [ "${pkgs.polkit_gnome}/libexec/polkit-gnome-authentication-agent-1" ]; }
      { argv = [ "${config.home.profileDirectory}/bin/noctalia-shell" ]; }
      { argv = [ "${pkgs.keepassxc}/bin/keepassxc" ]; }
      { argv = [ "${pkgs.mullvad-vpn}/bin/mullvad-vpn" ]; }
      {
        argv = [
          "${pkgs.wl-clipboard}/bin/wl-paste"
          "--type"
          "text"
          "--watch"
          "${pkgs.cliphist}/bin/cliphist"
          "store"
        ];
      }
      {
        argv = [
          "${pkgs.wl-clipboard}/bin/wl-paste"
          "--type"
          "image"
          "--watch"
          "${pkgs.cliphist}/bin/cliphist"
          "store"
        ];
      }
      {
        argv = [
          "${pkgs.wl-clip-persist}/bin/wl-clip-persist"
          "--clipboard"
          "regular"
        ];
      }

      { argv = [ "${config.home.homeDirectory}/.local/bin/librewolf-personal" ]; }
      { argv = [ "${constants.editor}" ]; }
      {
        argv = [
          "${constants.terminal}"
          "-e"
          "${config.home.profileDirectory}/bin/zellij-main"
        ];
      }
      { argv = [ "${pkgs.vesktop}/bin/vesktop" ]; }
      { argv = [ "${pkgs.telegram-desktop}/bin/Telegram" ]; }
    ];

    animations = {
      slowdown = 1.0;

      workspace-switch.kind.spring = mkSpring {
        dampingRatio = 1.0;
        stiffness = 1000;
        epsilon = 0.0001;
      };

      window-open.kind.easing = {
        duration-ms = 150;
        curve = "ease-out-expo";
      };

      window-close.kind.easing = {
        duration-ms = 150;
        curve = "ease-out-quad";
      };

      horizontal-view-movement.kind.spring = mkSpring {
        dampingRatio = 1.0;
        stiffness = 800;
        epsilon = 0.0001;
      };

      window-movement.kind.spring = mkSpring {
        dampingRatio = 1.0;
        stiffness = 800;
        epsilon = 0.0001;
      };

      window-resize.kind.spring = mkSpring {
        dampingRatio = 1.0;
        stiffness = 800;
        epsilon = 0.0001;
      };

      config-notification-open-close.kind.spring = mkSpring {
        dampingRatio = 0.6;
        stiffness = 1000;
        epsilon = 0.001;
      };
    };

    layer-rules = [
      (mkBackdropRule "^noctalia-wallpaper")
      (mkBackdropRule "^noctalia-overview")
    ];

    gestures.hot-corners.enable = false;

    # Required for Noctalia notification actions and window activation
    debug.honor-xdg-activation-with-invalid-serial = [ ];
  };
}
