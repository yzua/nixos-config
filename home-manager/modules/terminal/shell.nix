# Shared Bash/Zsh tools, local history, prompt, and Ghostty tmux sessions.

{ lib, ... }:

let
  aliases = {
    ".." = "cd ..";
    "..." = "cd ../..";
    "...." = "cd ../../..";
    "....." = "cd ../../../..";
    # Opt-in full-access launches; plain CLI names remain available for subcommands.
    cx = "codex --yolo";
    j = "just";
    killall = "pkill -f";
    ll = "ls -lah";
    mf = "microfetch";
    myip = "curl -s https://am.i.mullvad.net/ip";
    oc = "opencode --auto";
    open = "xdg-open";
    # Pi's tools already run without approval; this skips project trust for the run.
    p = "pi --approve";
  };
in
{
  programs.bash = {
    enable = true;
    # Bash is supplied by NixOS; Home Manager only owns its user configuration.
    package = null;
    shellAliases = aliases;
    # Match Zsh's ignore-space history; do not put secrets in commands regardless.
    historyControl = [ "ignoreboth" ];
  };

  programs.zsh = {
    enable = true;
    shellAliases = aliases;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;
    # Start tmux before loading the heavier interactive hooks in the outer shell.
    # Keep SSH, non-Ghostty shells, and tmux panes free of automatic attachment.
    initContent = lib.mkOrder 500 ''
      if [[ -o interactive && -z ''${TMUX-} && -z ''${SSH_CONNECTION-} && ''${TERM-} == xterm-ghostty ]] \
        && command -v tmux >/dev/null 2>&1; then
        tmux new-session -A -s main
      fi

      # Herdr manages persistent panes itself. Its palette replies can leak
      # into a child prompt when the client runs inside tmux 3.6.
      herdr() {
        if [[ $# -eq 0 && -n ''${TMUX-} && -z ''${SSH_CONNECTION-} && -n ''${WAYLAND_DISPLAY-} ]] \
          && command -v ghostty >/dev/null 2>&1; then
          env -u TMUX -u TMUX_PANE \
            -u HERDR_ENV -u HERDR_PANE_ID -u HERDR_SOCKET_PATH \
            -u HERDR_STARTUP_CWD -u HERDR_TAB_ID -u HERDR_WORKSPACE_ID \
            -u HERDR_BIN_PATH ghostty -e "$(whence -p herdr)"
        else
          command herdr "$@"
        fi
      }
      hd() { herdr "$@"; }
    '';
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
    # Focus reports trigger repeated palette queries in nested terminal apps.
    focusEvents = false;
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
