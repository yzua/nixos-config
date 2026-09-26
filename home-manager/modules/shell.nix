# Shared Bash/Zsh tools, local history, prompt, and Ghostty tmux sessions.

{ lib, ... }:

let
  aliases = {
    ".." = "cd ..";
    "..." = "cd ../..";
    "...." = "cd ../../..";
    "....." = "cd ../../../..";
    hd = "herdr";
    j = "just";
    killall = "pkill -f";
    ll = "ls -lah";
    mf = "microfetch";
    myip = "curl -s https://am.i.mullvad.net/ip";
    open = "xdg-open";
  };
  # Keep account-owned CLIs available in either interactive shell without
  # placing their mutable contents in the Nix store.
  localCliPath = ''
    export PATH="$HOME/.npm-global/bin:$PATH"
    export PATH="$HOME/.opencode/bin:$PATH"
  '';
in
{
  programs.bash = {
    enable = true;
    # Bash is supplied by NixOS; Home Manager only owns its user configuration.
    package = null;
    shellAliases = aliases;
    # Match Zsh's ignore-space history; do not put secrets in commands regardless.
    historyControl = [ "ignoreboth" ];
    bashrcExtra = localCliPath;
  };

  programs.zsh = {
    enable = true;
    shellAliases = aliases;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;
    # Start tmux before loading the heavier interactive hooks in the outer shell.
    # Keep SSH, non-Ghostty shells, and tmux panes free of automatic attachment.
    initContent = lib.mkMerge [
      (lib.mkOrder 500 ''
        if [[ -o interactive && -z ''${TMUX-} && -z ''${SSH_CONNECTION-} && ''${TERM-} == xterm-ghostty ]] \
          && command -v tmux >/dev/null 2>&1; then
          tmux new-session -A -s main
        fi
      '')
      localCliPath
    ];
  };

  programs.atuin = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = true;
    # Atuin owns Ctrl-R; preserve Up-arrow and do not bind the optional AI UI.
    flags = [
      "--disable-up-arrow"
      "--disable-ai"
    ];
    settings = {
      auto_sync = false;
      update_check = false;
      enter_accept = false;
      history_filter = [ "^ " ];
      inline_height = 20;
      logs.enabled = false;
      tmux.enabled = true;
    };
  };

  programs.starship = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = true;
    settings = {
      add_newline = false;
      format = "$directory$git_branch$git_status$nix_shell$cmd_duration$character";
      directory.style = "bold blue";
      git_branch = {
        format = "[$branch]($style) ";
        style = "bold purple";
      };
      git_status = {
        format = "([$all_status$ahead_behind]($style) )";
        style = "yellow";
      };
      nix_shell.format = "[nix $state]($style) ";
      cmd_duration.format = "[$duration]($style) ";
      character = {
        success_symbol = "[>](bold green)";
        error_symbol = "[>](bold red)";
      };
    };
  };

  programs.fzf = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = true;
  };

  programs.zoxide = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = true;
  };

  # direnv runs only for projects whose .envrc has been explicitly allowed.
  programs.direnv = {
    enable = true;
    enableBashIntegration = true;
    enableZshIntegration = true;
    nix-direnv.enable = true;
  };

  # Keep the familiar prefix and split keys; new panes inherit the current CWD.
  programs.tmux = {
    enable = true;
    baseIndex = 1;
    terminal = "tmux-256color";
    historyLimit = 10000;
    focusEvents = true;
    # Use Shift-drag for Ghostty text selection while tmux handles the mouse.
    mouse = true;
    extraConfig = ''
      set -g renumber-windows on
      set -g status-style 'bg=default,fg=default'
      set -g status-left ' #S '
      set -g status-right ' %H:%M '
      set -g window-status-current-style 'bold,fg=colour39'
      bind c new-window -c "#{pane_current_path}"
      bind '"' split-window -v -c "#{pane_current_path}"
      bind % split-window -h -c "#{pane_current_path}"
    '';
  };
}
