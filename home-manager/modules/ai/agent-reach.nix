# Keep Agent Reach managed by Nix; platform sessions remain private runtime state.
{ pkgs, ... }:

{
  home.packages = [ (pkgs.callPackage ../../../packages/agent-reach { }) ];
}
