# Niri window rules (floating, opacity, workspace assignments, positioning).

{ constants, ... }:
{
  programs.niri.settings.window-rules =
    let
      r = 0.0; # Square corners
      ws = import ./_workspace-names.nix;
      appIdMatch = pattern: { app-id = pattern; };
      mkFloatingRule = matches: {
        inherit matches;
        open-floating = true;
      };
      mkWorkspaceRule =
        matches: workspace: extra:
        {
          inherit matches;
          open-on-workspace = workspace;
        }
        // extra;
      mkWorkspaceAppIdRule =
        pattern: workspace: extra:
        mkWorkspaceRule [ (appIdMatch pattern) ] workspace extra;

      # LibreWolf profile app-ids (shared data from helpers).
      lwProfiles = import ../../_helpers/_librewolf-profiles.nix { inherit constants; };
      lwProfileNames = map (p: "librewolf-${p.name}") lwProfiles;
      lwBaseAppIds = [
        "librewolf"
        "librewolf-main"
      ];
      lwAllAppIds = lwBaseAppIds ++ lwProfileNames;
      lwNonI2pdAppIds =
        lwBaseAppIds ++ map (p: "librewolf-${p.name}") (builtins.filter (p: p.name != "i2pd") lwProfiles);

      # Build alternation regex from a list of literal strings: "^(a|b|c)$"
      mkAltRegex = ids: "^(${builtins.concatStringsSep "|" ids})$";
      # Without trailing $ anchor (for scroll-factor which also matches brave etc.)
      mkAltRegexOpen = ids: "^(${builtins.concatStringsSep "|" ids})";
    in
    [
      {
        geometry-corner-radius = {
          top-left = r;
          top-right = r;
          bottom-left = r;
          bottom-right = r;
        };
        clip-to-geometry = true;
      }

      (mkFloatingRule [ (appIdMatch "^io\\.github\\.celluloid_player\\.Celluloid$") ])
      (mkFloatingRule [ (appIdMatch "^io\\.bassi\\.Amberol$") ])
      (mkFloatingRule [ (appIdMatch "^imv$") ])
      (mkFloatingRule [ (appIdMatch "^showmethekey-gtk$") ])

      {
        matches = [
          {
            app-id = "^org\\.telegram\\.desktop$";
            title = "^Media viewer$";
          }
        ];
        open-floating = true;
      }

      (mkFloatingRule [ (appIdMatch "^org\\.gnome\\.NautilusPreviewer$") ])
      (mkFloatingRule [ (appIdMatch "^(pwvucontrol|nm-connection-editor|blueman-manager)$") ])
      {
        matches = [
          { app-id = "^org\\.gnome\\.Calculator$"; }
          { app-id = "^qalculate-gtk$"; }
        ];
        open-floating = true;
      }

      (mkWorkspaceRule [ (appIdMatch "^org\\.keepassxc\\.KeePassXC$") ] ws.vpn {
        open-floating = true;
      })
      {
        matches = [
          { app-id = "^xdg-desktop-portal-gtk$"; }
          { app-id = "^xdg-desktop-portal-gnome$"; }
        ];
        open-floating = true;
      }

      (mkFloatingRule [ { title = "^Picture-in-Picture$"; } ])
      {
        matches = [ { title = "^Picture-in-Picture$"; } ];
        default-floating-position = {
          x = 32;
          y = 32;
          relative-to = "bottom-right";
        };
        default-column-width.fixed = 480;
        default-window-height.fixed = 270;
      }
      (mkFloatingRule [ (appIdMatch "^scratchpad$") ])
      {
        matches = [ { app-id = "^(${constants.terminalAppId}|kitty|foot)$"; } ];
        opacity = 0.92;
      }
      {
        matches = [ { app-id = "^1password$"; } ];
        block-out-from = "screen-capture";
      }

      {
        matches = [ { app-id = "^xwaylandvideobridge$"; } ];
        opacity = 0.0;
        block-out-from = "screen-capture";
      }

      {
        matches = [ { is-floating = true; } ];
        shadow.enable = true;
      }
      {
        matches = [ { is-active = false; } ];
        opacity = 0.95;
      }

      {
        matches = [ { app-id = "^scratchpad$"; } ];
        default-floating-position = {
          x = 0;
          y = 0;
          relative-to = "top";
        };
        default-column-width = {
          proportion = 0.6;
        };
        default-window-height = {
          proportion = 0.4;
        };
      }

      {
        matches = [
          {
            app-id = mkAltRegexOpen (
              [
                "brave"
                "brave-browser"
                "firefox"
                "chromium"
              ]
              ++ lwAllAppIds
            );
          }
        ];
        scroll-factor = 0.75;
      }

      # Workspace assignments
      {
        matches = [
          {
            app-id = mkAltRegex lwNonI2pdAppIds;
          }
        ];
        open-on-workspace = ws.browser;
        default-column-width.proportion = 1.0;
      }
      (mkWorkspaceAppIdRule "^librewolf-i2pd$" ws.vpn {
        default-column-width.proportion = 1.0;
      })

      (mkWorkspaceAppIdRule "^(brave|brave-browser)$" ws.browser {
        default-column-width.proportion = 1.0;
      })

      (mkWorkspaceAppIdRule "^(${constants.editorAppId})$" ws.editor { })

      {
        matches = [ { app-id = "^(${constants.terminalAppId})$"; } ];
        excludes = [ { app-id = "^scratchpad$"; } ];
        open-on-workspace = ws.editor;
      }

      (mkWorkspaceAppIdRule "^vesktop$" ws.social { })

      {
        matches = [ { app-id = "^org\\.telegram\\.desktop$"; } ];
        excludes = [
          {
            app-id = "^org\\.telegram\\.desktop$";
            title = "^Media viewer$";
          }
        ];
        open-on-workspace = ws.social;
      }

      (mkWorkspaceAppIdRule "^FreeTube$" ws.media { })
      (mkWorkspaceAppIdRule "^muffon$" ws.media { })
      (mkWorkspaceAppIdRule "^nuclear$" ws.media { })
      {
        matches = [ { title = "^android-re"; } ];
        open-on-workspace = ws.android;
      }
      {
        matches = [ { title = "^web-re"; } ];
        open-on-workspace = ws.web-re;
      }
      (mkWorkspaceAppIdRule "^Emulator$" ws.android {
        open-floating = true;
      })
      (mkWorkspaceAppIdRule "^Mullvad VPN$" ws.vpn {
        open-floating = true;
      })
    ];
}
