# Install pinned skills.sh sources globally for every supported agent.

{
  aiPackages,
  lib,
  pkgs,
  ...
}:

let
  skillSources = [
    {
      url = "https://github.com/mattpocock/skills/tree/c55ee46073ed923f86ce59a5eb3b6d895095d1b7";
      name = "*";
    }
    {
      url = "https://github.com/ChromeDevTools/chrome-devtools-mcp/tree/ae0aaef884c41445d83f86f099ef211f4584b791/skills/chrome-devtools-cli";
      name = "chrome-devtools-cli";
    }
    {
      url = "https://github.com/iOfficeAI/OfficeCLI/tree/ffa8a0afbe2e9686abd636368e3da38c50f22131";
      name = "officecli";
    }
    {
      url = "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/477bcb28c9812b385cb51a4605ddf30d7b2266e2/.claude/skills";
      name = "*";
    }
  ];
  installCommands = lib.concatMapStringsSep "\n" (skill: ''
    ${lib.getExe aiPackages.skills} add ${lib.escapeShellArg skill.url} \
      --global --agent '*' --skill ${lib.escapeShellArg skill.name} --yes
  '') skillSources;
in
{
  # Home Manager removes its old skill links during linkGeneration. The
  # skills.sh CLI then owns the mutable copies and links for all agents.
  home.activation.installAgentSkills = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    if [ -v DRY_RUN ]; then
      echo "Would sync pinned skills.sh sources for all agents"
    else
      export PATH=${lib.makeBinPath [ pkgs.gitMinimal ]}:$PATH
      ${installCommands}
      # skills.sh links agents to this shared copy but does not rewrite Claude's plugin root.
      ${lib.getExe pkgs.python3} - "$HOME/.agents/skills/ui-ux-pro-max/SKILL.md" <<'PY'
    import sys
    from pathlib import Path
    path = Path(sys.argv[1])
    text = path.read_text()
    old = 'python "''${CLAUDE_PLUGIN_ROOT}/.claude/skills/ui-ux-pro-max/scripts/search.py"'
    new = f'{sys.executable} -B "{path.parent}/scripts/search.py"'
    if old not in text and new not in text:
        raise SystemExit("UI/UX search command changed upstream; review its script path")
    path.write_text(text.replace(old, new))
    PY
    fi
  '';
}
