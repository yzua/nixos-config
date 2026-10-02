# PipeWire audio stack with automatic RNNoise microphone filtering.

{ pkgs, ... }:

{
  services.pulseaudio.enable = false;
  security.rtkit.enable = true;

  services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    pulse.enable = true;

    # Expose the RNNoise LADSPA plugin to PipeWire without the other plugin formats.
    extraLadspaPackages = [ pkgs.rnnoise-plugin.ladspa ];
    extraConfig.pipewire."99-rnnoise-microphone" = {
      "context.modules" = [
        {
          name = "libpipewire-module-filter-chain";
          flags = [ "nofail" ];
          args = {
            "node.description" = "RNNoise microphone";
            "media.name" = "RNNoise microphone";
            "filter.graph".nodes = [
              {
                type = "ladspa";
                name = "rnnoise";
                plugin = "librnnoise_ladspa";
                label = "noise_suppressor_mono";
                control = {
                  "VAD Threshold (%)" = 50.0;
                  "VAD Grace Period (ms)" = 200;
                  "Retroactive VAD Grace (ms)" = 0;
                };
              }
            ];
            "capture.props" = {
              "node.name" = "capture.rnnoise_source";
              "node.passive" = true;
              "audio.rate" = 48000;
              "audio.channels" = 1;
              "audio.position" = [ "MONO" ];
            };
            "playback.props" = {
              "node.name" = "rnnoise_source";
              "media.class" = "Audio/Source";
              "audio.rate" = 48000;
              "audio.channels" = 1;
              "audio.position" = [ "MONO" ];
              # WirePlumber routes recordings through the filter for the chosen mic.
              "filter.smart" = true;
            };
          };
        }
      ];
    };
  };
}
