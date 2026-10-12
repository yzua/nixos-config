# Graphics driver selected by the flake setup, with 32-bit game support.

{ lib, setup, ... }:

{
  hardware.graphics = {
    enable = true;
    enable32Bit = true;
  };

  services.xserver.videoDrivers = setup.graphics.videoDrivers;

  # GPU monitoring and persistent fan control, independent of the desktop session.
  services.lact.enable = true;

  hardware.nvidia = lib.mkIf (builtins.elem "nvidia" setup.graphics.videoDrivers) {
    open = setup.graphics.nvidiaOpen;
    gsp.enable = setup.graphics.nvidiaGsp;
    moduleParams = lib.optionalAttrs (!setup.graphics.nvidiaGsp) {
      nvidia.NVreg_EnableGpuFirmware = 0;
    };
    modesetting.enable = true;
  };
}
