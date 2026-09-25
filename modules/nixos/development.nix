# Opt-in system-wide Node.js and pnpm development tools.

{ pkgs, ... }:

{
  environment.systemPackages = [
    pkgs.nodejs
    pkgs.pnpm
  ];
}
