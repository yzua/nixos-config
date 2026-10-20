# Preserve the native coding profile and history; pi remains its resume-aware alias.
{
  aiPackages,
  lib,
  pkgs,
  setup,
  ...
}:
let
  base = import ../pi-base/resources.nix { inherit aiPackages pkgs setup; };
  runtime = pkgs.writeText "pi-coding-runtime.json" (
    builtins.toJSON {
      inherit (base) pi;
      profile = "pi-coding";
      agentDir = ".pi/agent";
    }
  );
  coding = pkgs.writeShellScript "pi-coding-launch" ''
    exec ${pkgs.python3}/bin/python3 ${../pi-base/launcher.py} ${runtime} "$@"
  '';
  wrapper =
    name:
    lib.hiPrio (
      pkgs.writeShellScriptBin name ''
        exec ${pkgs.python3}/bin/python3 ${../pi-base/resume-dispatch.py} ${coding} -- "$@"
      ''
    );
in
{
  imports = [ ../pi-base ];
  home.packages = [
    (wrapper "pi")
    (wrapper "pi-coding")
  ];
  home.file = {
    ".pi/agent/prompts".source = ./prompts;
  };
}
