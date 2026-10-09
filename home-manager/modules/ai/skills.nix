# Prepare pinned skill sources before activation; skills.sh owns writable installed copies.

{
  aiPackages,
  lib,
  pkgs,
  ...
}:

let
  skillSources = [
    {
      owner = "mattpocock";
      repo = "skills";
      rev = "c55ee46073ed923f86ce59a5eb3b6d895095d1b7";
      hash = "sha256-L3CpIT2DeI+fUFl9fcygojtQo2DzEen69rMD1XqR1vM=";
      subdir = "";
      skill = "*";
    }
    {
      owner = "ChromeDevTools";
      repo = "chrome-devtools-mcp";
      rev = "ae0aaef884c41445d83f86f099ef211f4584b791";
      hash = "sha256-8lPhX9kG5iTiz1v9Ti8Hgs2oso/erkC7WlY3qk//mtg=";
      subdir = "/skills/chrome-devtools-cli";
      skill = "chrome-devtools-cli";
    }
    {
      owner = "iOfficeAI";
      repo = "OfficeCLI";
      rev = "ffa8a0afbe2e9686abd636368e3da38c50f22131";
      hash = "sha256-p+jwcgtRQJKSVWPxBO8F92xIAlLlDZxZ4fLwzJiZwZU=";
      subdir = "";
      skill = "officecli";
    }
    {
      owner = "nextlevelbuilder";
      repo = "ui-ux-pro-max-skill";
      rev = "477bcb28c9812b385cb51a4605ddf30d7b2266e2";
      hash = "sha256-vh9T4eqvexVzF9NqsASvTHrA43JSUkuEVQU17mERMSU=";
      subdir = "/.claude/skills";
      skill = "*";
      repairUiSearch = true;
    }
  ];
  sourceManifest = pkgs.writeText "agent-skills-sources.json" (
    builtins.toJSON (
      map (source: {
        path = "${
          pkgs.fetchFromGitHub {
            inherit (source)
              owner
              repo
              rev
              hash
              ;
          }
        }${source.subdir}";
        url = "https://github.com/${source.owner}/${source.repo}/tree/${source.rev}${source.subdir}";
        inherit (source) skill;
        repairUiSearch = source.repairUiSearch or false;
      }) skillSources
    )
  );
  preparedSkills = pkgs.runCommand "prepared-agent-skills" { } ''
    ${lib.getExe pkgs.python3} -B ${./skills.py} prepare ${sourceManifest} "$out"
  '';
in
{
  # Home Manager removes its old skill links during linkGeneration. Remote
  # fetching and text repair have already succeeded in the preview build.
  # skills.sh retains its mutable copies, all-agent discovery, and link policy.
  home.activation.installAgentSkills = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    ${lib.getExe pkgs.python3} -B ${./skills.py} install \
      ${lib.escapeShellArg (toString preparedSkills)} ${lib.escapeShellArg (lib.getExe aiPackages.skills)}
  '';
}
