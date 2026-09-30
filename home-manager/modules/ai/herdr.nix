# Configure Herdr and its pinned Smart Rename plugin without storing credentials.

{
  aiPackages,
  lib,
  pkgs,
  ...
}:

let
  smartRenameSource = pkgs.fetchFromGitHub {
    owner = "iurysza";
    repo = "herdr-tab-smart-rename";
    rev = "9947873333c0786360f02a491c905f7bc194e1c4";
    hash = "sha256-I6Hzh+qJy3wupdke54SMfAh1Afcb3RFKsIN9mIb97us=";
  };
  # Fetch the frozen production dependencies; lifecycle scripts never run.
  smartRenameDependencies = pkgs.stdenvNoCC.mkDerivation {
    pname = "herdr-smart-rename-dependencies";
    version = "0.6.0";
    src = smartRenameSource;
    nativeBuildInputs = [ pkgs.bun ];
    dontConfigure = true;
    dontBuild = true;
    dontFixup = true;
    installPhase = ''
      bun install --frozen-lockfile --production --ignore-scripts \
        --backend copyfile --cache-dir "$TMPDIR/bun-cache"
      cp -R node_modules "$out"
    '';
    outputHashMode = "recursive";
    outputHashAlgo = "sha256";
    outputHash = "sha256-nlokDxXMUbUo/DopGgsLCGsAl9JUVhZ6Wqp0XHTlc5k=";
  };
  smartRename = pkgs.runCommand "herdr-smart-rename-0.6.0" { } ''
    pluginDir="$out/share/herdr/plugins/smart-rename"
    mkdir -p "$pluginDir"
    cp -R ${smartRenameSource}/. "$pluginDir/"
    chmod -R u+w "$pluginDir"
    # Keep the node_modules directory name in resolved paths for package imports.
    cp -R ${smartRenameDependencies} "$pluginDir/node_modules"
    ${lib.getExe pkgs.python3} - "$pluginDir/herdr-plugin.toml" \
      ${lib.getExe pkgs.bun} ${lib.getExe pkgs.bash} <<'PY'
    import json
    import pathlib
    import sys

    manifest = pathlib.Path(sys.argv[1])
    text = manifest.read_text()
    build = '[[build]]\ncommand = ["bun", "install", "--production", "--frozen-lockfile"]\n\n'
    if build not in text:
        raise SystemExit("Smart Rename's build manifest changed; review its dependencies")
    text = text.replace(build, "").replace('["bun",', '[' + json.dumps(sys.argv[2]) + ',')
    # Restore the worker with its Herdr session once a model has been selected.
    startup = 'if [ -s "$HERDR_PLUGIN_CONFIG_DIR/model-selection.json" ]; then exec ' + sys.argv[2] + ' src/cli.ts start; fi'
    text += '\n[[startup]]\ncommand = ' + json.dumps([sys.argv[3], "-c", startup]) + '\n'
    manifest.write_text(text)
    PY
  '';
  herdr = lib.getExe aiPackages.herdr;
in

{
  # The bundled Codex SessionStart hook silently skips reporting without python3.
  home.packages = [
    pkgs.python3
    pkgs.bun
    smartRename
  ];

  # Herdr owns the registry and private model selection; Nix owns plugin code.
  home.activation.registerHerdrSmartRename = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    run ${herdr} plugin link ${smartRename}/share/herdr/plugins/smart-rename
    rename_config=$(${herdr} plugin config-dir tab-smart-rename)
    if [ -s "$rename_config/model-selection.json" ]; then
      run ${herdr} plugin action invoke start --plugin tab-smart-rename
    fi
  '';

  xdg.configFile."herdr/config.toml".text = ''
    onboarding = false

    [theme]
    name = "terminal"
    auto_switch = false

    [ui]
    status_indicators = "symbols"
    agent_panel_sort = "priority"
    prompt_new_tab_name = false

    [ui.toast]
    delivery = "system"
    delay_seconds = 1

    [update]
    version_check = false

    [[keys.command]]
    key = "prefix+r"
    type = "plugin_action"
    command = "tab-smart-rename.rename-now"
    description = "Name this tab from its current task"
  '';
}
