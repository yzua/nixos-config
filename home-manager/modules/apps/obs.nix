# OBS Studio configuration with essential plugins.

{ pkgs, ... }:

let
  capturePlugins = with pkgs.obs-studio-plugins; [
    input-overlay # Display keyboard/mouse input
    wlrobs # Wayland screen capture
    obs-pipewire-audio-capture # PipeWire audio capture
    obs-vkcapture # Vulkan/OpenGL game capture
    obs-gstreamer # GStreamer integration for more sources
    obs-vaapi # VA-API hardware encoding (AMD/Intel)
  ];

  effectsPlugins = with pkgs.obs-studio-plugins; [
    obs-backgroundremoval # AI background removal
    obs-move-transition # Smooth animated transitions between scenes
    obs-shaderfilter # Custom shader effects
  ];

  automationPlugins = with pkgs.obs-studio-plugins; [
    obs-source-record # Record individual sources separately
    advanced-scene-switcher # Automate scene switching
  ];
in

{
  programs.obs-studio = {
    enable = true;

    package = pkgs.obs-studio;

    plugins = capturePlugins ++ effectsPlugins ++ automationPlugins;
  };
}
