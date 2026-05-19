# LibreWolf browser with declarative baseline policies, multi-profile proxy setup, and extensions.
# Each profile is fully isolated with its own proxy - never mix proxies.

{
  pkgsStable,
  lib,
  constants,
  ...
}:
let
  extensionPolicies = import ./_extensions.nix;
  profileSpecs = import ../../../_helpers/_librewolf-profiles.nix { inherit constants; };
  baseSettings = {
    "app.update.auto" = false;
    "browser.shell.checkDefaultBrowser" = false;
    "browser.startup.page" = 1;
    "browser.newtabpage.enabled" = true;
    "browser.privatebrowsing.autostart" = false;
    "browser.compactmode.show" = true;
    "browser.uidensity" = 1;
    "browser.toolbars.bookmarks.visibility" = "newtab";
    "browser.tabs.loadInBackground" = true;
    "browser.tabs.warnOnClose" = false;
    "browser.tabs.closeWindowWithLastTab" = false;

    # Theme
    "extensions.activeThemeID" = "{1e01c787-99d2-4826-86df-0003da8e88cd}";
    "layout.css.prefers-color-scheme.content-override" = 0;
    "toolkit.legacyUserProfileCustomizations.stylesheets" = true;
    "layout.css.moz-document.content.enabled" = true;

    # Sidebar - disabled for Sidebery
    "sidebar.revamp" = false;
    "sidebar.verticalTabs" = false;
    "sidebar.visibility" = "hide-sidebar";

    # Privacy
    "media.peerconnection.enabled" = false;
    "network.cookie.lifetimePolicy" = 0;
    "privacy.clearOnShutdown.cookies" = false;
    "privacy.clearOnShutdown.offlineApps" = false;
    "privacy.clearOnShutdown.history" = false;
    "privacy.clearOnShutdown.cache" = false;
    "privacy.sanitize.sanitizeOnShutdown" = false;

    # Anti-fingerprinting
    "privacy.resistFingerprinting" = true; # Resist canvas/font/WebGL fingerprinting
    "privacy.fingerprintingProtection" = true; # Firefox fingerprinting protection
    "privacy.fingerprintingProtection.overrides" = ""; # No overrides
    "privacy.trackingprotection.enabled" = true; # Enhanced Tracking Protection
    "privacy.trackingprotection.socialtracking.enabled" = true; # Block social trackers
    "privacy.trackingprotection.cryptomining.enabled" = true; # Block cryptominers
    "privacy.trackingprotection.fingerprinting.enabled" = true; # Block fingerprinters
    "privacy.firstparty.isolate" = true; # First-party isolation (no cross-site tracking)
    "privacy.query_stripping.enabled" = true; # Strip tracking params from URLs
    "privacy.query_stripping.strip_list" =
      "utm_source utm_medium utm_campaign utm_term utm_content fbclid gclid dclid twclid";
    "webgl.disabled" = true; # Disable WebGL (fingerprint vector)
    "geo.enabled" = false; # Disable geolocation API
    "media.navigator.enabled" = false; # Disable JS media device enumeration

    # Proxy base config (host set per-profile)
    "network.proxy.type" = 1;
    "network.proxy.socks_port" = constants.ports.socks;
    "network.proxy.socks_version" = 5;
    "network.proxy.socks_remote_dns" = true;

    # ytmpv protocol handler
    "network.protocol-handler.external.ytmpv" = true;
    "network.protocol-handler.expose.ytmpv" = false;
    "network.protocol-handler.warn-external.ytmpv" = false;
  };

  # Generate launcher script for a profile.
  mkLauncher = name: profilePath: {
    ".local/bin/librewolf-${name}" = {
      executable = true;
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail
        if [ "$#" -gt 0 ]; then
          exec ${pkgsStable.librewolf}/bin/librewolf \
            --name librewolf-${name} \
            --profile "$HOME/.librewolf/${profilePath}" \
            --new-tab "$1"
        fi

        exec ${pkgsStable.librewolf}/bin/librewolf \
          --new-instance \
          --name librewolf-${name} \
          --profile "$HOME/.librewolf/${profilePath}"
      '';
    };
  };

  # Generate chrome file symlinks for a profile.
  mkChromeFiles = profilePath: {
    ".librewolf/${profilePath}/chrome/userChrome.css".source =
      ../../../../themes/librewolf-userChrome.css;
    ".librewolf/${profilePath}/chrome/userContent.css".source =
      ../../../../themes/librewolf-userContent.css;
  };

  mkProfile = spec: {
    inherit (spec)
      id
      isDefault
      path
      ;
    settings =
      baseSettings
      // {
        "browser.startup.homepage" = spec.homepage;
        "network.proxy.socks" = spec.proxyHost;
      }
      // (spec.extraSettings or { });
  };

  librewolfProfileFiles = builtins.listToAttrs (
    lib.flatten (
      map (
        spec:
        (lib.mapAttrsToList (name: value: { inherit name value; }) (mkLauncher spec.name spec.path))
        ++ (lib.mapAttrsToList (name: value: { inherit name value; }) (mkChromeFiles spec.path))
      ) profileSpecs
    )
  );

  generatedProfiles = builtins.listToAttrs (
    map (spec: {
      inherit (spec) name;
      value = mkProfile spec;
    }) profileSpecs
  );
in
{
  home.file = librewolfProfileFiles // {
    ".librewolf/profiles.ini".force = true;
  };

  programs.librewolf = {
    enable = true;
    package = pkgsStable.librewolf;

    policies = {
      DisableTelemetry = true;
      DisableFirefoxStudies = true;
      DisablePocket = true;
      DisableFirefoxAccounts = true;
      DontCheckDefaultBrowser = true;
      OfferToSaveLogins = false;
      PasswordManagerEnabled = false;
      inherit (extensionPolicies) ExtensionSettings;
      UserMessaging = {
        ExtensionRecommendations = false;
        SkipOnboarding = true;
      };
    };

    profiles = generatedProfiles;
  };

}
