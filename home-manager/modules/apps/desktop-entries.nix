# Desktop entries and launcher wrapper scripts for desktop applications.

{
  config,
  constants,
  pkgs,
  user,
  ...
}:

let

  mkDesktopEntry =
    {
      name,
      exec,
      icon,
      comment,
      categories,
      mimeType ? null,
    }:
    {
      inherit
        name
        exec
        icon
        comment
        categories
        ;
    }
    // (if mimeType == null then { } else { inherit mimeType; });

  librewolfDesktopProfiles = import ../../_helpers/_librewolf-profiles.nix { inherit constants; };

  librewolfDesktopEntries = builtins.listToAttrs (
    map (profile: {
      name = "librewolf-${profile.name}";
      value = mkDesktopEntry {
        name = "LibreWolf ${profile.label}";
        exec = "${homeDir}/.local/bin/librewolf-${profile.name} %U";
        icon = "librewolf";
        inherit (profile) comment;
        categories = [ "Network" ];
      };
    }) librewolfDesktopProfiles
  );
  homeDir = config.home.homeDirectory;
in

{
  home.file = import ./_desktop-local-bin-wrappers.nix { inherit pkgs user; };

  home.packages = [
    pkgs.wofi
  ];

  xdg.desktopEntries = {
    "youtube-mpv" = mkDesktopEntry {
      name = "YouTube MPV";
      exec = "${homeDir}/.local/bin/youtube-mpv %U";
      icon = "mpv";
      comment = "Open YouTube links in mpv";
      categories = [
        "AudioVideo"
        "Player"
      ];
      mimeType = [ "x-scheme-handler/ytmpv" ];
    };
    "element-desktop" = mkDesktopEntry {
      name = "Element";
      exec = "${homeDir}/.local/bin/element-desktop-keyring %u";
      icon = "element-desktop";
      comment = "Matrix client with libsecret keyring backend";
      categories = [
        "Network"
        "InstantMessaging"
        "Chat"
      ];
      mimeType = [
        "x-scheme-handler/element"
        "x-scheme-handler/io.element.desktop"
        "x-scheme-handler/matrix"
      ];
    };

    # === Brave ===
    "brave-proxy" = mkDesktopEntry {
      name = "Brave";
      exec = "${homeDir}/.local/bin/brave-proxy %U";
      icon = "brave";
      comment = "Brave with Finland proxy";
      categories = [ "Network" ];
    };
  }
  // librewolfDesktopEntries;
}
