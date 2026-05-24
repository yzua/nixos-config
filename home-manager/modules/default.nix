# Home Manager modules aggregation.

{
  imports = [
    # Desktop environment
    ./niri # Niri compositor (scrollable tiling Wayland)
    ./noctalia # Noctalia Shell (bar, launcher, notifications, OSD)
    ./stylix.nix # Theming engine (Gruvbox base16, fonts, cursor, icons)
    ./qt.nix # Qt theming (Kvantum + Gruvbox)
    ./mime.nix # MIME type default application associations
    # Terminal and shell
    ./terminal # Shell, terminal emulator, CLI tools

    # Development
    ./ai-agents # AI coding agents (Claude Code, OpenCode, Codex, Antigravity)
    ./programming-languages # Language tooling (Go, JS/TS, Python)
    ./neovim # Neovim editor with LSP and plugins

    # Applications
    ./apps # App configs (OBS, Syncthing, KeePassXC, etc.)

    # Security
    ./gpg.nix # GnuPG agent and key configuration
    ./ssh.nix # SSH client hardening (algorithms, forwarding, host keys)

    # Privacy
    ./telemetry.nix # Telemetry and tracking opt-out variables
  ];
}
