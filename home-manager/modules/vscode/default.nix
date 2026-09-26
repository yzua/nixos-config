# VS Code with Nix-managed extensions and editor preferences.

{
  config,
  lib,
  pkgs,
  ...
}:

let
  extensions = pkgs.vscode-extensions;
  settings = (pkgs.formats.json { }).generate "vscode-settings" (
    import ./settings.nix { inherit pkgs; }
  );
  settingsPath = "${config.xdg.configHome}/Code/User/settings.json";
  backupRoot = "${config.xdg.stateHome}/nixos";
in
{
  # The editor font is installed for this user rather than assumed to exist.
  home.packages = [ pkgs.jetbrains-mono ];
  fonts.fontconfig.enable = true;

  # Home Manager's userSettings option links settings.json into the read-only
  # store. Extensions write to that file, so install a writable Nix baseline
  # after Home Manager removes the previous generation's managed symlink.
  home.activation.vscodeWritableSettings = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    target=${lib.escapeShellArg settingsPath}
    if [ -v DRY_RUN ]; then
      echo "Would install writable VS Code settings at $target after linking"
    else
      if [ -L "$target" ] || { [ -e "$target" ] && [ ! -f "$target" ]; }; then
        echo "VS Code settings path is not a regular file: $target" >&2
        exit 1
      fi

      if [ ! -f "$target" ] || ! cmp -s ${settings} "$target"; then
        mkdir -p "$(dirname "$target")"
        if [ -f "$target" ]; then
          mkdir -p ${lib.escapeShellArg backupRoot}
          backupDir="$(mktemp -d ${lib.escapeShellArg "${backupRoot}/vscode-settings.XXXXXXXX"})"
          cp -p "$target" "$backupDir/settings.json"
          echo "Backed up previous VS Code settings to $backupDir/settings.json"
        fi
        tmp="$(mktemp "$(dirname "$target")/.settings.json.XXXXXXXX")"
        cp ${settings} "$tmp"
        chmod 600 "$tmp"
        mv -f "$tmp" "$target"
      fi
      chmod 600 "$target"
    fi
  '';

  programs.vscode = {
    enable = true;
    # VS Code cannot install/update extensions in a Nix-managed directory.
    mutableExtensionsDir = false;

    profiles.default = {
      # Use Nixpkgs' pinned VSIXes instead of maintaining Marketplace hashes.
      extensions = [
        # Nix and project environments.
        extensions.jnoortheen.nix-ide
        extensions.mkhl.direnv

        # Python, Go, Rust, and Zig.
        extensions.ms-python.python
        extensions.ms-python.debugpy
        extensions.detachhead.basedpyright
        extensions.charliermarsh.ruff
        extensions.golang.go
        extensions.rust-lang.rust-analyzer
        extensions.vadimcn.vscode-lldb
        extensions.ziglang.vscode-zig

        # Web development: built-in JS/TS plus formatting and language tooling.
        extensions.biomejs.biome
        extensions.yoavbls.pretty-ts-errors
        extensions.svelte.svelte-vscode
        extensions.bradlc.vscode-tailwindcss
        extensions.ecmel.vscode-html-css
        extensions.pranaygp.vscode-css-peek
        extensions.vitest.explorer

        # Shell, data formats, and documentation.
        extensions.timonwong.shellcheck
        extensions.foxundermoon.shell-format
        extensions.redhat.vscode-yaml
        extensions.tamasfe.even-better-toml
        extensions.mikestead.dotenv
        extensions.davidanson.vscode-markdownlint
        extensions.yzhang.markdown-all-in-one

        # Git, navigation, and familiar appearance.
        extensions.editorconfig.editorconfig
        extensions.eamodio.gitlens
        extensions.usernamehw.errorlens
        extensions.gruntfuggly.todo-tree
        extensions.christian-kohler.path-intellisense
        extensions.jdinhlife.gruvbox
        extensions.vscode-icons-team.vscode-icons
      ];
    };
  };
}
