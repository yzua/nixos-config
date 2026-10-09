# Set the user's file, web, messaging, and torrent MIME and URL-handler defaults.

let
  firefox = "firefox.desktop";
  telegram = "org.telegram.desktop.desktop";
  qbittorrent = "org.qbittorrent.qBittorrent.desktop";
  textEditor = "code.desktop";
  papers = "org.gnome.Papers.desktop";
  loupe = "org.gnome.Loupe.desktop";
  decibels = "org.gnome.Decibels.desktop";
  showtime = "org.gnome.Showtime.desktop";
  nautilus = "org.gnome.Nautilus.desktop";

  # xdg-open's generic desktop path does not inherit text/plain defaults for
  # these types; define them explicitly so these files do not fall back to a browser.
  textDefaults = builtins.listToAttrs (
    map
      (mime: {
        name = mime;
        value = textEditor;
      })
      [
        "text/plain"
        "text/markdown"
        "text/x-markdown"
        "text/csv"
        "text/tab-separated-values"
        "text/x-log"
        "text/css"
        "text/x-scss"
        "text/javascript"
        "application/javascript"
        "application/json"
        "application/schema+json"
        "application/ld+json"
        "application/xml"
        "text/xml"
        "application/yaml"
        "application/x-yaml"
        "text/yaml"
        "text/x-yaml"
        "application/toml"
        "application/sql"
        "text/x-csharp"
        "text/x-patch"
        "application/x-shellscript"
        "text/x-shellscript"
        "text/x-python"
        "text/x-python3"
        "text/x-csrc"
        "text/x-chdr"
        "text/x-c++src"
        "text/x-c++hdr"
        "text/x-java"
        "text/x-go"
        "text/rust"
        "text/x-rust"
        "text/x-makefile"
        "text/x-cmake"
        "text/x-lua"
        "text/x-perl"
        "application/x-ruby"
        "application/x-php"
      ]
  );

  defaults = textDefaults // {
    # Web and Telegram links.
    "x-scheme-handler/http" = firefox;
    "x-scheme-handler/https" = firefox;
    "x-scheme-handler/chrome" = firefox;
    "text/html" = firefox;
    "application/x-extension-htm" = firefox;
    "application/x-extension-html" = firefox;
    "application/x-extension-shtml" = firefox;
    "application/xhtml+xml" = firefox;
    "application/x-extension-xhtml" = firefox;
    "application/x-extension-xht" = firefox;
    "x-scheme-handler/tg" = telegram;
    "x-scheme-handler/tonsite" = telegram;

    # Torrent downloads and magnet links.
    "application/x-bittorrent" = qbittorrent;
    "x-scheme-handler/magnet" = qbittorrent;

    # Folders, documents, and images. File URIs use the target's MIME type.
    "inode/directory" = nautilus;
    "application/pdf" = papers;
    "image/jpeg" = loupe;
    "image/png" = loupe;
    "image/webp" = loupe;
    "image/svg+xml" = loupe;

    # Audio and video.
    "audio/mpeg" = decibels;
    "audio/x-flac" = decibels;
    "video/mp4" = showtime;
    "video/webm" = showtime;
    "video/x-matroska" = showtime;

    # Archives (GNOME Files handles quick extraction).
    "application/zip" = nautilus;
    "application/x-7z-compressed" = nautilus;
    "application/vnd.rar" = nautilus;
  };
in
{
  xdg.mimeApps = {
    enable = true;
    defaultApplications = defaults;
    associations.added = defaults;
  };
}
