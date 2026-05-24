# Custom package derivations.

{
  imports = [
    ./antigravity-cli.nix # Antigravity CLI agent (agy)
    ./beads.nix # Beads git-backed issue tracker (bd CLI)
    ./chrome-devtools.nix # Chrome DevTools MCP CLI wrapper
    ./cursor.nix # Cursor terminal agent CLI
    ./kiro.nix # Kiro CLI for agentic workflows
    ./prayer.nix # Custom prayer times indicator
  ];
}
