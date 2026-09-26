# VS Code with Nix-managed extensions and editor preferences.

{ pkgs, ... }:

let
  extensions = pkgs.vscode-extensions;
in
{
  # The editor font is installed for this user rather than assumed to exist.
  home.packages = [ pkgs.jetbrains-mono ];
  fonts.fontconfig.enable = true;

  programs.vscode = {
    enable = true;
    # VS Code cannot install/update extensions in a Nix-managed directory.
    mutableExtensionsDir = false;

    profiles.default = {
      enableUpdateCheck = false;
      enableExtensionUpdateCheck = false;
      userSettings = import ./settings.nix { inherit pkgs; };

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
