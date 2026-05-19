# Gaming support (Steam, Lutris, Wine, MangoHud).

{
  config,
  lib,
  pkgs,
  ...
}:

{
  options.mySystem.gaming = {
    enable = lib.mkEnableOption "gaming support with Steam and related tools";

    enableGamemode = lib.mkEnableOption "Feral GameMode for automatic per-game CPU/GPU optimizations";

    enableGamescope = lib.mkEnableOption "gamescope session for Steam with better frame timing, VRR support, and upscaling";
  };

  config = lib.mkIf config.mySystem.gaming.enable {
    programs = {
      steam = {
        enable = true;
        gamescopeSession.enable = config.mySystem.gaming.enableGamescope;
        extraCompatPackages = with pkgs; [ proton-ge-bin ];
      };

      gamescope = lib.mkIf config.mySystem.gaming.enableGamescope {
        enable = true;
        capSysNice = true;
      };

      gamemode = lib.mkIf config.mySystem.gaming.enableGamemode {
        enable = true;
        settings = {
          general = {
            renice = 10; # Renice game process for priority
            softrealtime = "auto"; # SCHED_ISO when available
            inhibit_screensaver = 1;
          };
          gpu = {
            apply_gpu_optimisations = "accept-responsibility";
            gpu_device = 1; # NVIDIA GPU is card1 (card0 has no vendor file)
            nv_powermizer_mode = 1; # Prefer maximum performance
          };
          custom = {
            start = "${pkgs.libnotify}/bin/notify-send 'GameMode' 'Optimizations activated'";
            end = "${pkgs.libnotify}/bin/notify-send 'GameMode' 'Optimizations deactivated'";
          };
        };
      };
    };

    environment = {
      sessionVariables = {
        # Standard Steam path for third-party compatibility tools (Proton-GE, etc.)
        STEAM_EXTRA_COMPAT_TOOLS_PATHS = "\${HOME}/.steam/root/compatibilitytools.d";
        # MangoHud default overlay config
        MANGOHUD_CONFIG = "fps,frametime,gpu_stats,gpu_temp,cpu_stats,cpu_temp,ram,vram";
      };

      systemPackages = with pkgs; [
        mangohud # Vulkan/OpenGL overlay for FPS, frame timing, GPU stats
        protonup-ng # Proton-GE version manager
        lutris # Multi-platform game launcher
        steam-run # FHS environment for running non-Nix Linux games
        wine # Windows compatibility layer
        winetricks # Wine configuration helper
        libunwind # Stack unwinding library required by some Proton games
      ];
    };
  };
}
