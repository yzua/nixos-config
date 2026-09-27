# Package the voice-action bridge and its Pi instructions.

{ aiPackages, pkgs }:

pkgs.writeShellApplication {
  name = "voxtype-pi-action";
  runtimeInputs = [
    aiPackages.pi
    aiPackages.voxtype
    pkgs.coreutils
    pkgs.libnotify
    pkgs.util-linux
  ];
  text = ''
    export VOICE_ACTION_PROMPT=${./action.md}
    ${builtins.readFile ./action.sh}
  '';
}
