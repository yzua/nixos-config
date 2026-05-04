# Glance GitHub token bootstrap for authenticated widgets.

{
  lib,
  pkgs,
  user,
}:

let
  ghBin = lib.getExe pkgs.gh;
  extractToken = pkgs.writeShellScriptBin "glance-github-token" ''
    if GH_TOKEN=$(systemd-run --user --uid=${user} --pipe ${ghBin} auth token 2>/dev/null); then
      printf 'GITHUB_TOKEN=%s\n' "$GH_TOKEN" > /run/glance/github-token.env
    else
      echo "⚠ gh CLI not authenticated - GitHub widgets will not work"
      printf 'GITHUB_TOKEN=\n' > /run/glance/github-token.env
    fi
  '';
in
{
  serviceConfig = {
    ExecStartPre = [ "+${lib.getExe extractToken}" ];
    EnvironmentFile = lib.mkForce "-/run/glance/github-token.env";
    SupplementaryGroups = [ "docker" ];
  };
}
