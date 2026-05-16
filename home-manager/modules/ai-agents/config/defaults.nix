# Base AI agent defaults: enablement, shared instructions, and skill sets.

_:

let
  skillDefs = import ./_skills.nix;
in
{
  programs.aiAgents = {
    enable = true;
    globalInstructions = builtins.readFile ./global-instructions.md;
    everythingClaudeCode.enable = true;
    agencyAgents.enable = false;
    impeccable.enable = true;
    terax.enable = true;
    agentmemory.enable = true;

    inherit (skillDefs) skills;
  };
}
