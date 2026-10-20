# Start playback-only EasyEffects with a gentle headset EQ and a flat fallback.

{
  lib,
  pkgs,
  setup,
  ...
}:

let
  inherit (setup) audio;
  audioReady = import ../desktop/audio-ready.nix { inherit pkgs; };
  audioServices = [
    "pipewire.service"
    "pipewire-pulse.service"
    "wireplumber.service"
  ];
  presetName = "headset-gentle";
  flatName = "unprocessed";
  json = pkgs.formats.json { };
  autoloadFile = lib.replaceStrings [ "/" ] [ "_" ] "${audio.playbackDevice}:${audio.playbackRoute}";
  band = type: frequency: gain: {
    inherit type frequency gain;
    mode = "RLC (BT)";
    slope = "x1";
    q = 0.707;
    width = 4.0;
    solo = false;
    mute = false;
  };
  # A preference starting point, not a measured correction or Windows emulation.
  channel = {
    band0 = band "Lo-shelf" 100.0 2.0;
    band1 = band "Bell" 300.0 (-1.5);
    band2 = band "Bell" 3000.0 1.0;
  };
  configure = pkgs.writeShellApplication {
    name = "easyeffects-playback-settings";
    runtimeInputs = [ pkgs.kdePackages.kconfig ];
    text = ''
      # Keep the app's settings writable, including its global bypass switch.
      main=easyeffects/db/easyeffectsrc
      kwriteconfig6 --file "$main" --group EffectsPipelines --key processAllInputs --type bool false
      kwriteconfig6 --file "$main" --group EffectsPipelines --key processAllOutputs --type bool true
      # Never carry a previous headset chain into startup on a different output.
      kwriteconfig6 --file "$main" --group StreamOutputs --key plugins ""
      kwriteconfig6 --file "$main" --group Window --key autostartOnLogin --type bool false
      kwriteconfig6 --file "$main" --group Window --key outputAutoloadingUsesFallback --type bool true
      kwriteconfig6 --file "$main" --group Window --key outputAutoloadingFallbackPreset ${flatName}
      kwriteconfig6 --file "$main" --group StreamInputs --key listenToMic --type bool false
      kwriteconfig6 --file "$main" --group StreamInputs --key listenToMicIncludesOutputEffects --type bool false
    '';
  };
in
{
  services.easyeffects = {
    enable = true;
    extraPresets = {
      ${flatName}.output = {
        blocklist = [ ];
        plugins_order = [ ];
      };
      ${presetName}.output = {
        blocklist = [ ];
        plugins_order = [ "equalizer#0" ];
        "equalizer#0" = {
          bypass = false;
          # Headroom for the small boosts; do not raise the physical volume.
          "input-gain" = -4.0;
          "output-gain" = 0.0;
          "num-bands" = 3;
          mode = "IIR";
          "split-channels" = false;
          balance = 0.0;
          "pitch-left" = 0.0;
          "pitch-right" = 0.0;
          left = channel;
          right = channel;
        };
      };
    };
  };

  # EasyEffects 8 uses the active route's description, not its internal name.
  xdg.dataFile."easyeffects/autoload/output/${autoloadFile}.json".source =
    json.generate "headset-autoload.json"
      {
        device = audio.playbackDevice;
        "device-description" = "Configured headset";
        "device-profile" = audio.playbackRoute;
        "preset-name" = presetName;
      };

  # Home Manager owns login startup; disable the app's duplicate autostart.
  systemd.user.services.easyeffects = {
    Unit = {
      After = audioServices;
      Wants = audioServices;
    };
    # Ordering alone does not wait for WirePlumber's default/ports enumeration.
    # On timeout, fail before EasyEffects can intercept streams; systemd retries.
    Service.ExecStartPre = [
      (lib.getExe audioReady)
      (lib.getExe configure)
    ];
  };
}
