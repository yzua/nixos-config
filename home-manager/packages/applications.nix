# Desktop applications, multimedia, productivity, and theming packages.

{ pkgs, ... }:

{
  home.packages = with pkgs; [
    (bottles.override { removeWarningPopup = true; })
    code-cursor-fhs
    element-desktop
    google-chrome
    imv
    kiro-fhs
    localsend
    libreoffice-qt6-fresh
    sqlitebrowser
    keepassxc
    antigravity-fhs

    # Minecraft
    (prismlauncher.override {
      additionalLibs = [
        libdecor
        libxkbcommon
        wayland
      ];
      additionalPrograms = [
        libdecor
        libxkbcommon
        wayland
      ];
    })
    fabric-installer

    # Messaging
    signal-desktop
    telegram-desktop

    # VPN GUIs
    proton-vpn

    # Torrents
    qbittorrent

    # GTK theming
    gnome-themes-extra
    gruvbox-gtk-theme

    # Multimedia
    amberol # GNOME audio player
    ffmpeg # Multimedia processing toolkit
    jpegoptim # JPEG lossless optimization
    mediainfo # Media file analyzer
    optipng # PNG lossless optimization
    freetube # YouTube client
    muffon # Desktop music streaming and discovery client
    nuclear # Privacy-focused music player and discovery

    # Productivity
    porsmo # CLI Pomodoro timer
    watson # Project-based time tracking
    timewarrior # Taskwarrior companion
  ];
}
