# Set the user's web and Telegram MIME and URL-handler defaults.

let
  firefox = "firefox.desktop";
  telegram = "org.telegram.desktop.desktop";

  # Keep existing browser and Telegram defaults together in one place.
  defaults = {
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
  };
in
{
  xdg.mimeApps = {
    enable = true;
    defaultApplications = defaults;
    associations.added = defaults;
  };
}
