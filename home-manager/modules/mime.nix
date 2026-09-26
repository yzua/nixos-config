# Set the user's file, web, and Telegram MIME and URL-handler defaults.

let
  firefox = "firefox.desktop";
  telegram = "org.telegram.desktop.desktop";
  textEditor = "org.gnome.TextEditor.desktop";
  papers = "org.gnome.Papers.desktop";
  loupe = "org.gnome.Loupe.desktop";
  decibels = "org.gnome.Decibels.desktop";
  showtime = "org.gnome.Showtime.desktop";
  nautilus = "org.gnome.Nautilus.desktop";

  defaults = {
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

    # Documents and images.
    "text/plain" = textEditor;
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
