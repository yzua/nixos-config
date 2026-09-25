# Link pinned skill bundles into agents' global skill directories.

{ lib, mattPocockSkills, ... }:

let
  # Discover all upstream SKILL.md bundles (including newly added ones on a
  # targeted input update), keeping their companion scripts/assets together.
  skillFiles = builtins.filter (file: builtins.baseNameOf file == "SKILL.md") (
    lib.filesystem.listFilesRecursive (mattPocockSkills + "/skills")
  );
  skills = map (file: {
    # The directory name is plain text, not a reference to a store path.
    name = builtins.unsafeDiscardStringContext (builtins.baseNameOf (builtins.dirOf file));
    source = builtins.dirOf file;
  }) skillFiles;
  skillNames = map (skill: skill.name) skills;

  # Shared by Codex (including the ChatGPT desktop Codex surface), OpenCode,
  # Pi, and Copilot. Claude Code and Antigravity require their own global dirs.
  destinations = [
    ".agents/skills"
    ".claude/skills"
    ".gemini/config/skills"
    ".gemini/antigravity-cli/skills"
  ];
in
{
  assertions = [
    {
      assertion = skills != [ ] && builtins.length skillNames == builtins.length (lib.unique skillNames);
      message = "Matt Pocock's skills must contain SKILL.md files with unique directory names";
    }
  ];

  # Individual links leave manually installed skills and agent configs alone.
  home.file = lib.listToAttrs (
    lib.concatMap (
      destination:
      map (skill: {
        name = "${destination}/${skill.name}";
        value.source = skill.source;
      }) skills
    ) destinations
  );
}
