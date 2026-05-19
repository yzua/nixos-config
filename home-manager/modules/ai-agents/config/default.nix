# Import hub for split AI agent configuration files.

{
  imports = [
    ./defaults.nix # Enablement, shared instructions, and skill defaults
    ./_shell-env.nix # modules-check: manual-helper Computed shell env for external modules
    ./mcp-servers.nix # MCP server definitions and logging
    ./mcp-servers-android-re.nix # Android RE agent-specific MCP servers (not shared globally)
    ./mcp-servers-web-re.nix # Web RE agent-specific MCP servers (not shared globally)
    ./models # Model/provider registries (OpenCode, Codex, Gemini)
    ./claude # Claude Code permissions, hooks, and settings
  ];
}
