# Install pinned AI applications while leaving their mutable data unmanaged.

{ aiPackages, pkgs, ... }:

let
  # Codex 0.157 enables daemon auto-start, but this source-built package lacks
  # the complete-package metadata needed to launch the daemon. Override only
  # this feature for the CLI until the upstream packaging is fixed; leave the
  # user's mutable Codex config and credentials outside Nix.
  codexCli = pkgs.symlinkJoin {
    name = "codex-no-auto-daemon";
    paths = [ aiPackages.codex ];
    nativeBuildInputs = [ pkgs.makeWrapper ];
    postBuild = ''
      wrapProgram "$out/bin/codex" --add-flags "--disable daemon_auto_start"
    '';
  };
in
{
  # Executables come from Numtide; settings, logins, and session data remain
  # in the user's home until deliberately migrated one app at a time.
  home.packages = with aiPackages; [
    antigravity-cli
    chatgpt
    claude-code
    claude-desktop
    codexCli
    copilot-cli
    ctx
    executor
    opencode2
    pi
    skills
    t3code-desktop
    zcode
  ];
}
