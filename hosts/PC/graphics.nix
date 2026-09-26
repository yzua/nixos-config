# PC's RTX 2070: NVIDIA driver and Wayland graphics support.

{
  hardware.graphics = {
    enable = true;
    enable32Bit = true;
  };

  services.xserver.videoDrivers = [ "nvidia" ];

  hardware.nvidia = {
    # The RTX 2070 is Turing; NVIDIA recommends its open kernel modules.
    open = true;
    modesetting.enable = true;
  };
}
