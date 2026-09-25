# Manage Personal and Work Firefox profiles with shared search and preferences.

let
  search = {
    default = "ddg";
    privateDefault = "ddg";
    # Firefox rewrites search.json.mozlz4 after launch.
    force = true;
  };

  settings = {
    "browser.newtabpage.activity-stream.showSponsored" = false;
    "browser.newtabpage.activity-stream.showSponsoredTopSites" = false;
    "browser.urlbar.suggest.quicksuggest.sponsored" = false;
    "media.autoplay.default" = 1; # Block audible autoplay.
    "privacy.globalprivacycontrol.enabled" = true;
  };
in
{
  programs.firefox = {
    enable = true;
    profiles = {
      personal = {
        id = 0;
        isDefault = true;
        inherit search settings;
      };

      work = {
        id = 1;
        isDefault = false;
        inherit search settings;
      };
    };
  };
}
