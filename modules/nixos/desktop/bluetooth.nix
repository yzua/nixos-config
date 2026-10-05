# Enable Bluetooth adapters and provide a desktop pairing manager.

{
  hardware.bluetooth = {
    enable = true;
    powerOnBoot = true;
  };

  # Provide pairing/trust controls in Niri as well as GNOME's built-in UI.
  services.blueman.enable = true;

  # AirPods media buttons need WirePlumber's AVRCP player, not mpris-proxy.
  services.pipewire.wireplumber.extraConfig."51-bluetooth-media-controls" = {
    "monitor.bluez.properties" = {
      "bluez5.dummy-avrcp-player" = true;
    };
  };
}
