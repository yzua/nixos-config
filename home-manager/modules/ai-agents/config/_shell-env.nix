# Computed shell environment values for external modules (zsh, niri).
# Provides programs.aiAgents.shellEnv — read-only data consumed via config.

{ config, ... }:

let
  zai = import ../helpers/_zai.nix { };
  opencodeProfiles = import ../helpers/_opencode-profiles.nix { inherit config; };
in
{
  programs.aiAgents.shellEnv = {
    zaiInlinePrefix = zai.inlinePrefix;
    opencodeProfileData = opencodeProfiles.profiles;
  };
}
