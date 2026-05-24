# AI coding agents configuration (Claude Code, OpenCode, Codex, Antigravity CLI).

{ ... }:
{
  imports = [
    ./options.nix # Option definitions for programs.aiAgents
    ./activation # Activation scripts (secret patching, config setup, plugin installs)
    ./files.nix # home.file and xdg.configFile declarations
    ./packages.nix # Packages, zsh aliases, systemd services/timers, log analysis
    ./config # Actual agent configuration values
  ];
}
