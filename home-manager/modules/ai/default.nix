# Add desktop AI applications and larger workloads to the shared coding tools.

{ aiPackages, ... }:

{
  imports = [
    ./cli.nix
    ./herdr-backup.nix
    ./open-design.nix
    ./pi-re
    ./voice
  ];

  # Settings, logins, and session data remain writable and outside Nix.
  home.packages = with aiPackages; [
    antigravity-cli
    chatgpt
    ctx
    t3code-desktop
    zcode
  ];
}
