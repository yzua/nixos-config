# Manage Personal and Work Firefox profiles with shared add-ons, search, and preferences.

{ pkgs, ... }:

let
  # Keep official AMO XPIs intact so Firefox can verify their signatures.
  firefoxAddon =
    {
      name,
      id,
      url,
      hash,
    }:
    pkgs.runCommand "firefox-addon-${name}" { } ''
      extensionDir="$out/share/mozilla/extensions/{ec8030f7-c20a-464f-9b0e-13a3a9e97384}"
      mkdir -p "$extensionDir"
      cp ${pkgs.fetchurl { inherit url hash; }} "$extensionDir/${id}.xpi"
    '';

  extensions.packages = map firefoxAddon [
    # GitHub
    {
      name = "enhanced-github-6.1.0";
      id = "{72bd91c9-3dc5-40a8-9b10-dec633c0873f}";
      url = "https://addons.mozilla.org/firefox/downloads/file/4297236/enhanced_github-6.1.0.xpi";
      hash = "sha256-jr8v92AuF0fzzDKefJms9zSNAZ7EVuVjnZ2Qrwt6/sM=";
    }
    {
      name = "octotree-8.3.1";
      id = "jid1-Om7eJGwA1U8Akg@jetpack";
      url = "https://addons.mozilla.org/firefox/downloads/file/5059273/octotree-8.3.1.xpi";
      hash = "sha256-2KqhHHTa8JMEeSYvbRdNGUFmQCInx/eYga2uOsf0W2I=";
    }
    {
      name = "refined-github-26.9.12";
      id = "{a4c4eda4-fb84-4a84-b4a1-f7c1cbf2a1ad}";
      url = "https://addons.mozilla.org/firefox/downloads/file/5024350/refined_github-26.9.12.xpi";
      hash = "sha256-7/YBFTqyjxmsO82ktdjz+Mj060esRd3ao6SaZ7c0E40=";
    }

    # Privacy and security
    {
      name = "ublock-origin-1.75.0";
      id = "uBlock0@raymondhill.net";
      url = "https://addons.mozilla.org/firefox/downloads/file/5034826/ublock_origin-1.75.0.xpi";
      hash = "sha256-W3RBWGBFY3BkS9gPFhJehlsObDVrtd/PuEBpln6qUoc=";
    }
    {
      name = "simplelogin-3.0.7";
      id = "addon@simplelogin";
      url = "https://addons.mozilla.org/firefox/downloads/file/4458602/simplelogin-3.0.7.xpi";
      hash = "sha256-jpHQt+K8dnRoGN2MxTPqUlucPP1DP7pS2kdmqD9Xne0=";
    }
    {
      name = "canvas-blocker-no-fingerprint-0.2.4";
      id = "{e98b4b87-bc39-439f-a175-b15fbe4a06c0}";
      url = "https://addons.mozilla.org/firefox/downloads/file/4764176/canvas_blocker_no_fingerprint-0.2.4.xpi";
      hash = "sha256-TPHyFnJQ9g8jSQyw3K1fQzyVhEo40zrUe/YMACuIetw=";
    }
    {
      name = "privacy-badger-2026.9.15";
      id = "jid1-MnnxcxisBPnSXQ@jetpack";
      url = "https://addons.mozilla.org/firefox/downloads/file/5032646/privacy_badger17-2026.9.15.xpi";
      hash = "sha256-l82JEeNIbaNKUyp8fygGzW0M+hF6H75eh0cEKpRELWI=";
    }

    # Web development and display
    {
      name = "sidebery-5.6.1";
      id = "{3c078156-979c-498b-8990-85f7987dd929}";
      url = "https://addons.mozilla.org/firefox/downloads/file/4903712/sidebery-5.6.1.xpi";
      hash = "sha256-6KCktVarfdU2iXwYFq+dCRgDAiMGjqZoOgQ3YQOmyvI=";
    }
    {
      name = "darkreader-4.9.133";
      id = "addon@darkreader.org";
      url = "https://addons.mozilla.org/firefox/downloads/file/5055786/darkreader-4.9.133.xpi";
      hash = "sha256-6wbFCW12FhbH8dlUwRUkykv/T+cikETcH84oiowIU6s=";
    }
    # The old JSON Viewer is Chrome-only; JSONView is its Firefox equivalent.
    {
      name = "jsonview-3.2.0";
      id = "jsonview@brh.numbera.com";
      url = "https://addons.mozilla.org/firefox/downloads/file/4494774/jsonview-3.2.0.xpi";
      hash = "sha256-D/+04I5eFuj9WYwU/XKnd3EdyUG+VN+AMXx1R0LKmUI=";
    }
    {
      name = "wappalyzer-6.12.6";
      id = "wappalyzer@crunchlabz.com";
      url = "https://addons.mozilla.org/firefox/downloads/file/4982523/wappalyzer-6.12.6.xpi";
      hash = "sha256-OjaeVYChtIZAAcAh4PW1JKfwiWi0OPt9XXy+iH6M7ok=";
    }

    # YouTube and social
    {
      name = "return-youtube-dislikes-4.0.6";
      id = "{762f9885-5a13-4abd-9c77-433dcd38b8fd}";
      url = "https://addons.mozilla.org/firefox/downloads/file/5012638/return_youtube_dislikes-4.0.6.xpi";
      hash = "sha256-WXGXSfbfOMFgHKXznAIVjV8AXEPp7uofGVJ/RoyUEhc=";
    }
    {
      name = "unhook-1.6.9";
      id = "myallychou@gmail.com";
      url = "https://addons.mozilla.org/firefox/downloads/file/4733035/youtube_recommended_videos-1.6.9.xpi";
      hash = "sha256-Rrv0C3gazjI3cf8ZPF3ieFtBDV2INkH48Hw5Oo+W1pw=";
    }
    {
      name = "control-panel-for-twitter-4.24.2";
      id = "{5cce4ab5-3d47-41b9-af5e-8203eea05245}";
      url = "https://addons.mozilla.org/firefox/downloads/file/5048223/control_panel_for_twitter-4.24.2.xpi";
      hash = "sha256-xz7U9mOoPjXJvZbi59K++FtOtMFl1tlM46Hyo/5lueg=";
    }
    {
      name = "sponsorblock-6.1.7";
      id = "sponsorBlocker@ajay.app";
      url = "https://addons.mozilla.org/firefox/downloads/file/4897574/sponsorblock-6.1.7.xpi";
      hash = "sha256-DVDhYyxvFe4VpUPmcOHFcpdGBaXAJiKRbgjgJoA9+D8=";
    }
  ];

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
  stylix.targets.firefox = {
    profileNames = [
      "personal"
      "work"
    ];
    firefoxGnomeTheme.enable = true;
  };

  programs.firefox = {
    enable = true;
    profiles = {
      personal = {
        id = 0;
        isDefault = true;
        inherit extensions search settings;
      };

      work = {
        id = 1;
        isDefault = false;
        inherit extensions search settings;
      };
    };
  };
}
