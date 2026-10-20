# Share one unchanged Chrome DevTools skill pin between Pi base and skills.sh installation.
{ pkgs }:
let
  source = {
    owner = "ChromeDevTools";
    repo = "chrome-devtools-mcp";
    rev = "ae0aaef884c41445d83f86f099ef211f4584b791";
    hash = "sha256-8lPhX9kG5iTiz1v9Ti8Hgs2oso/erkC7WlY3qk//mtg=";
    subdir = "/skills/chrome-devtools-cli";
    skill = "chrome-devtools-cli";
  };
in
{
  inherit source;
  directory = pkgs.runCommand "pi-chrome-devtools-cli-skill" { } ''
    mkdir -p "$out"
    cp -r ${
      pkgs.fetchFromGitHub {
        inherit (source)
          owner
          repo
          rev
          hash
          ;
      }
    }${source.subdir}/. "$out/"
    test -f "$out/SKILL.md"
    test -f "$out/references/installation.md"
  '';
}
