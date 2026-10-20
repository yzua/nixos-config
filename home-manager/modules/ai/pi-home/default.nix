# Personal Pi profile: base tools, separate history and on-demand Samsung TV control.
{
  aiPackages,
  pkgs,
  setup,
  ...
}:
let
  base = import ../pi-base/resources.nix { inherit aiPackages pkgs setup; };
  instructions = pkgs.writeText "pi-home-instructions.md" (
    builtins.readFile base.instructions + "\n" + builtins.readFile ./AGENTS.md
  );
  tvPython = pkgs.python3.withPackages (ps: [ ps.samsungtvws ]);
  tvConfig = pkgs.writeText "pi-home-tv.json" (builtins.toJSON setup.pi.home.samsung);
  runtime = pkgs.writeText "pi-home-runtime.json" (
    builtins.toJSON {
      inherit (base) pi commonExtensions;
      profile = "pi-home";
      agentDir = ".pi/agent";
      sessions = "pi-home/sessions";
      instructions = [ instructions ];
      skills = base.commonSkills ++ [ ./skills/samsung-tv ];
      tvPython = "${tvPython}/bin/python3";
      tvScript = ./tv.py;
      inherit tvConfig;
    }
  );
in
{
  imports = [ ../pi-base ];
  home.packages = [
    (pkgs.writeShellScriptBin "pi-home" ''
      exec ${pkgs.python3}/bin/python3 ${../pi-base/launcher.py} ${runtime} "$@"
    '')
  ];
}
