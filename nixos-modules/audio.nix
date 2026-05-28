# PipeWire audio stack (ALSA, PulseAudio compat, JACK, RNNoise).

{ pkgs, ... }:

let
  rnnoise = pkgs.rnnoise-plugin;
in
{
  security.rtkit.enable = true;

  services = {
    pulseaudio.enable = false;

    pipewire = {
      enable = true;
      alsa.enable = true;
      alsa.support32Bit = true;
      pulse.enable = true;
      jack.enable = true;
      extraLadspaPackages = [ rnnoise ];

      extraConfig.pipewire = {
        # Increase buffer size to reduce audio stuttering in Electron apps (pear-desktop).
        # Default quantum=256 causes xruns; 1024 absorbs scheduling jitter.
        "91-buffer-size" = {
          "context.properties" = {
            "default.clock.quantum" = 1024;
            "default.clock.min-quantum" = 512;
          };
        };

        # RNNoise mic noise cancellation for video calls
        "99-rnnoise" = {
          "context.modules" = [
            {
              name = "libpipewire-module-filter-chain";
              args = {
                "node.description" = "Noise Cancelling Source";
                "media.name" = "Noise Cancelling Source";
                "filter.graph" = {
                  nodes = [
                    {
                      type = "ladspa";
                      name = "rnnoise";
                      plugin = "librnnoise_ladspa";
                      label = "noise_suppressor_stereo";
                      control = {
                        "VAD Threshold (%)" = 50.0;
                      };
                    }
                  ];
                };
                "capture.props" = {
                  "node.name" = "effect_input.rnnoise";
                  "node.passive" = true;
                };
                "playback.props" = {
                  "node.name" = "effect_output.rnnoise";
                  "media.class" = "Audio/Source";
                };
              };
            }
          ];
        };
      };
    };
  };

  environment.systemPackages = [ pkgs.rnnoise-plugin ];
}
