# Public immutable base resources; profiles select policy, never rebuild common extensions.
{
  aiPackages,
  pkgs,
  setup,
}:
let
  bundle = import ./extension-resources.nix { inherit pkgs setup; };
  directory = "${bundle}/lib/pi-config";
  extensionNames = [
    "ask-user-question.ts"
    "network-diagnostics.ts"
    "codex-lb-session.ts"
    "upstream-retry.ts"
    "our-free-model.ts"
    "prompt-snippets"
    "web-fetch"
    "web-search"
    "interactive-subagents"
  ];
  entryPoints = {
    interactive-subagents = "/pi-extension/subagents/index.ts";
  };
in
{
  inherit bundle directory extensionNames;
  commonSkills = [ (import ./chrome-skill.nix { inherit pkgs; }).directory ];
  pi = pkgs.lib.getExe aiPackages.pi;
  # Herdr manages its coding reporter itself. Explicit-load roots use its pinned copy.
  commonExtensions = [
    "${aiPackages.herdr}/share/herdr/integrations/pi/herdr-agent-state.ts"
  ]
  ++ map (
    name:
    "${directory}/${name}${
      entryPoints.${name} or (if pkgs.lib.hasSuffix ".ts" name then "" else "/index.ts")
    }"
  ) extensionNames;
  instructions = ./AGENTS.md;
}
