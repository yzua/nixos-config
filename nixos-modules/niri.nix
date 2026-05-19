# Niri scrollable tiling Wayland compositor.

{
  lib,
  pkgs,
  inputs,
  ...
}:

{
  imports = [ inputs.niri.nixosModules.niri ];

  # Add niri overlay for mesa compatibility
  nixpkgs.overlays = [ inputs.niri.overlays.niri ];

  programs.niri = {
    enable = true;
    package = pkgs.niri;
  };

  # XWayland compatibility via xwayland-satellite
  environment.systemPackages = [ pkgs.xwayland-satellite ];

  # Security services for compositor
  security.polkit.enable = true;

  # niri-flake's user service runs outside the compositor session on this host,
  # causing polkit-gnome to loop with "No session for pid". Start the agent
  # from Niri startup (home-manager/modules/niri/main.nix) instead.
  systemd.user.services.niri-flake-polkit.enable = lib.mkForce false;

}
