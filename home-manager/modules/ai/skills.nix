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
    fi
  '';
}
