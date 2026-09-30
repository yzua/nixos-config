# Install pinned AI applications and import agent settings without managing mutable data.

{
  aiPackages,
  pkgs,
  ...
}:

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
  # Numtide's V2 package exposes `opencode2`; provide the usual CLI name and
  # generate matching Zsh completion from that package.
  opencodeCli = pkgs.symlinkJoin {
    name = "opencode-cli";
    paths = [
      (pkgs.writeShellScriptBin "opencode" ''
        exec ${aiPackages.opencode2}/bin/opencode2 "$@"
      '')
    ];
    postBuild = ''
      mkdir -p "$out/share/zsh/site-functions"
      HOME="$TMPDIR" \
        XDG_CONFIG_HOME="$TMPDIR/config" \
        XDG_DATA_HOME="$TMPDIR/data" \
        XDG_CACHE_HOME="$TMPDIR/cache" \
        XDG_STATE_HOME="$TMPDIR/state" \
        ${aiPackages.opencode2}/bin/opencode2 --completions zsh > "$out/share/zsh/site-functions/_opencode"
    '';
  };
in
{
  imports = [
    ./herdr.nix
    ./pnpm-tools.nix
    ./pi
    ./skills.nix
    ./voice
  ];

  # Executables come from Numtide; settings, logins, and session data remain
  # in the user's home until deliberately migrated one app at a time.
  home.packages = with aiPackages; [
    antigravity-cli
    chatgpt
    codexCli
    ctx
    executor
    herdr
    officecli
    opencodeCli
    opencode2
    pi
    skills
    t3code-desktop
    zcode
  ];
}
