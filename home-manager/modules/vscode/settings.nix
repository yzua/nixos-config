# VS Code's default profile; Home Manager owns settings.json as a read-only symlink.

{ pkgs }:

let
  ignoredDirs = [
    ".direnv"
    "node_modules"
    "result"
    "target"
    ".zig-cache"
  ];
  ignored = builtins.listToAttrs (
    map (dir: {
      name = "**/${dir}";
      value = true;
    }) ignoredDirs
  );
  unwatched = builtins.listToAttrs (
    map (dir: {
      name = "**/${dir}/**";
      value = true;
    }) ignoredDirs
  );
in
{
  # Keep the old layout and theme, without copying extension defaults.
  "workbench.colorTheme" = "Gruvbox Dark Soft";
  "workbench.iconTheme" = "vscode-icons";
  "workbench.activityBar.location" = "top";
  "workbench.sideBar.location" = "right";
  "workbench.layoutControl.enabled" = false;
  "workbench.navigationControl.enabled" = false;
  "workbench.startupEditor" = "none";
  "window.commandCenter" = false;
  "window.menuBarVisibility" = "toggle";
  "window.titleBarStyle" = "custom";
  "window.zoomLevel" = 0.5;
  "chat.commandCenter.enabled" = false;

  "editor.fontFamily" = "'JetBrains Mono', 'Noto Color Emoji', monospace";
  "editor.fontSize" = 13;
  "editor.fontLigatures" = true;
  "editor.minimap.enabled" = false;
  "editor.renderWhitespace" = "boundary";
  "editor.guides.bracketPairs" = "active";
  "editor.smoothScrolling" = true;
  "editor.cursorSmoothCaretAnimation" = "on";
  "editor.cursorBlinking" = "smooth";
  "editor.linkedEditing" = true;
  "editor.stickyScroll.enabled" = true;
  "editor.tabSize" = 2;
  "editor.insertSpaces" = true;
  "editor.formatOnSave" = true;
  "files.autoSave" = "afterDelay";
  "files.autoSaveDelay" = 1000;
  "files.trimTrailingWhitespace" = true;
  "files.insertFinalNewline" = true;
  "files.trimFinalNewlines" = true;
  "files.exclude" = ignored // {
    "**/__pycache__" = true;
  };
  "files.watcherExclude" = unwatched;
  "search.exclude" = ignored;

  "terminal.integrated.fontFamily" = "'JetBrains Mono'";
  "terminal.integrated.fontSize" = 13;
  "terminal.integrated.defaultProfile.linux" = "zsh";
  "explorer.sortOrder" = "type";
  "explorer.compactFolders" = false;
  "git.autofetch" = true;
  "git.enableCommitSigning" = true;

  # Pin editor-owned tools to the same Nixpkgs input as the extensions.
  "nix.enableLanguageServer" = true;
  "nix.serverPath" = "${pkgs.nixd}/bin/nixd";
  "nix.serverSettings".nixd.formatting.command = [ "${pkgs.nixfmt}/bin/nixfmt" ];
  # The Python extension still handles debugging; BasedPyright supplies the LSP.
  "python.languageServer" = "None";
  "basedpyright.analysis.typeCheckingMode" = "basic";
  "basedpyright.analysis.autoImportCompletions" = true;
  "basedpyright.disableOrganizeImports" = true;
  "[python]" = {
    "editor.defaultFormatter" = "charliermarsh.ruff";
    "editor.codeActionsOnSave" = {
      "source.fixAll.ruff" = "explicit";
      "source.organizeImports.ruff" = "explicit";
    };
  };
  "go.alternateTools".gopls = "${pkgs.gopls}/bin/gopls";
  "go.toolsManagement.autoUpdate" = false;
  "[go]"."editor.defaultFormatter" = "golang.go";
  "zig.path" = "${pkgs.zig}/bin/zig";
  "zig.zls.path" = "${pkgs.zls}/bin/zls";
  "[zig]" = {
    "editor.defaultFormatter" = "ziglang.vscode-zig";
    "editor.tabSize" = 4;
  };
  "rust-analyzer.check.command" = "clippy";
  "[rust]" = {
    "editor.defaultFormatter" = "rust-lang.rust-analyzer";
    "editor.tabSize" = 4;
  };

  "[javascript]"."editor.defaultFormatter" = "biomejs.biome";
  "[javascriptreact]"."editor.defaultFormatter" = "biomejs.biome";
  "[typescript]"."editor.defaultFormatter" = "biomejs.biome";
  "[typescriptreact]"."editor.defaultFormatter" = "biomejs.biome";
  "[json]"."editor.defaultFormatter" = "biomejs.biome";
  "[jsonc]"."editor.defaultFormatter" = "biomejs.biome";
  "[svelte]"."editor.defaultFormatter" = "svelte.svelte-vscode";
  "[toml]"."editor.defaultFormatter" = "tamasfe.even-better-toml";
  "[shellscript]"."editor.defaultFormatter" = "foxundermoon.shell-format";
  "shellcheck.executablePath" = "${pkgs.shellcheck}/bin/shellcheck";
  "shellformat.path" = "${pkgs.shfmt}/bin/shfmt";
  "[markdown]" = {
    "editor.wordWrap" = "on";
    "files.trimTrailingWhitespace" = false;
  };
  "tailwindCSS.classAttributes" = [
    "class"
    "className"
    "ngClass"
    "class:list"
  ];
  "todo-tree.general.tags" = [
    "BUG"
    "HACK"
    "FIXME"
    "TODO"
    "XXX"
    "NOTE"
    "PERF"
    "SAFETY"
  ];

  # The package and extensions update through Nix, never from within Code.
  "update.mode" = "none";
  "extensions.autoCheckUpdates" = false;
  "extensions.autoUpdate" = false;
  "vsicons.dontShowNewVersionMessage" = true;
  "update.showReleaseNotes" = false;
  "settingsSync.enable" = false;
  "telemetry.telemetryLevel" = "off";
}
