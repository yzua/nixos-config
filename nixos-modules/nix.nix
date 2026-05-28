# Nix package manager configuration (flakes, GC, binary caches).

{
  config,
  inputs,
  lib,
  pkgConfig,
  nixpkgsOverlays,
  ...
}:

{
  # Mirror pkgConfig from flake.nix — nixosSystem evaluates its own nixpkgs instance
  nixpkgs.config = pkgConfig;
  nixpkgs.overlays = nixpkgsOverlays;

  nix = {
    daemonCPUSchedPolicy = "batch";
    daemonIOSchedClass = "idle";

    nixPath = [ "nixpkgs=${inputs.nixpkgs}" ];
    channel.enable = false;

    # Pin flake registry to our nixpkgs -- avoids network lookups for `nix run nixpkgs#<pkg>`
    registry.nixpkgs.flake = inputs.nixpkgs;

    extraOptions = ''
      warn-dirty = false
    '';

    settings = {
      experimental-features = [
        "nix-command"
        "flakes"
        "pipe-operators"
      ];

      # SECURITY: Restrict Nix daemon access
      allowed-users = [ "@wheel" ];
      trusted-users = [
        "root"
        "@wheel"
      ];

      auto-optimise-store = true;
      download-buffer-size = 262144000; # 250 MB

      keep-outputs = true;
      keep-derivations = true;
      sandbox = true;
      sandbox-fallback = false;

      max-jobs = "auto";
      cores = 0;
      max-substitution-jobs = 8;
      http-connections = 25;

      substituters = [
        "https://cache.nixos.org?priority=10"
        "https://nix-community.cachix.org"
        "https://numtide.cachix.org"
      ]
      ++ lib.optionals config.mySystem.nvidia.enable [
        "https://cuda-maintainers.cachix.org"
      ];

      trusted-public-keys = [
        "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
        "numtide.cachix.org-1:2ps1kLBUWjxIneOy1Ik6cQjb41X0iXVXeHigGmycPPE="
      ]
      ++ lib.optionals config.mySystem.nvidia.enable [
        "cuda-maintainers.cachix.org-1:0dq3bujKpuEPMCX6U4WylrUDZ9JyUG0VpVZa7CNfq5E="
      ];
    };

    gc = {
      automatic = true;
      persistent = true;
      dates = "weekly";
      options = "--delete-older-than 7d";
    };
  };
}
