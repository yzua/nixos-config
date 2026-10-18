# Share coding CLIs and agent integrations without the desktop-only AI workloads.

{
  aiPackages,
  pkgs,
  ...
}:

let
  # The source-built Codex package lacks daemon auto-start metadata.
  codexCli = pkgs.symlinkJoin {
    name = "codex-no-auto-daemon";
    paths = [ aiPackages.codex ];
    nativeBuildInputs = [ pkgs.makeWrapper ];
    postBuild = ''
      wrapProgram "$out/bin/codex" --add-flags "--disable daemon_auto_start"
    '';
  };
  # Keep the usual CLI name and completion for Numtide's V2 package.
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
    ./chrome-devtools
    ./pi
    ./skills.nix
  ];

  home.file.".codex/AGENTS.md".source = ./agent-instructions.md;
  xdg.configFile."opencode/AGENTS.md".source = ./agent-instructions.md;

  home.packages = with aiPackages; [
    codexCli
    herdr
    officecli
    opencodeCli
    pi
    skills
  ];
}
