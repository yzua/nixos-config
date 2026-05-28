# NVIDIA GPU drivers, CUDA, and Wayland integration.

{
  config,
  lib,
  pkgs,
  ...
}:

let
  nvidiaDriverChannel = config.boot.kernelPackages.nvidiaPackages.stable;
in
{
  options.mySystem.nvidia = {
    enable = lib.mkEnableOption "NVIDIA GPU drivers and CUDA support";
  };

  config = lib.mkIf config.mySystem.nvidia.enable {
    services.xserver.videoDrivers = [ "nvidia" ];

    boot = {
      kernelParams = [
        "nvidia-drm.modeset=1"
        "nvidia-drm.fbdev=1" # Framebuffer device for console resolution and VT switching on Wayland
        "nvidia.NVreg_PreserveVideoMemoryAllocations=1" # Preserve GPU memory on suspend/resume
      ];
      blacklistedKernelModules = [ "nouveau" ];
    };

    environment.variables = {
      LIBVA_DRIVER_NAME = "nvidia";
      XDG_SESSION_TYPE = "wayland";
      GBM_BACKEND = "nvidia-drm";
      __GLX_VENDOR_LIBRARY_NAME = "nvidia";

      # Force GTK4 apps to use GL renderer instead of Vulkan.
      # Fixes black/broken windows with NVIDIA (VK_ERROR_OUT_OF_DATE_KHR).
      GSK_RENDERER = "gl";

      # ELECTRON_OZONE_PLATFORM_HINT is set in niri/main.nix (compositor-level)
      __GL_GSYNC_ALLOWED = "1";
      __GL_VRR_ALLOWED = "1";
      NVD_BACKEND = "direct";
      MOZ_ENABLE_WAYLAND = "1";
    };

    nixpkgs.config.nvidia.acceptLicense = true;

    hardware = {
      nvidia = {
        open = true;
        nvidiaSettings = true;
        modesetting.enable = true; # Required for Wayland compositors
        package = nvidiaDriverChannel;

        powerManagement = {
          enable = true;
          # finegrained configured in host-specific modules
        };
      };

      graphics = {
        enable = true;
        package = nvidiaDriverChannel;
        enable32Bit = true;

        extraPackages = with pkgs; [
          nvidia-vaapi-driver
          libva-vdpau-driver
          libvdpau-va-gl
          mesa
          egl-wayland
          vulkan-loader
          libva
        ];
      };
    };

    environment.systemPackages = with pkgs; [
      vulkan-tools
      mesa-demos
      libva-utils
    ];

    # PRIVACY: NVIDIA proprietary drivers may collect usage telemetry.
    # As of driver 570+, no known user-facing telemetry toggle exists.

    services.udev.extraRules = ''
      KERNEL=="nvidia*", GROUP="video", MODE="0660"
      KERNEL=="nvidiactl", GROUP="video", MODE="0660"
      KERNEL=="nvidia-modeset", GROUP="video", MODE="0660"
    '';
  };
}
