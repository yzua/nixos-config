# Shared Bash/Zsh tools, local history, prompt, and Ghostty tmux sessions.

{
  config,
  lib,
  pkgs,
  ...
}:

let
  colors = config.lib.stylix.colors.withHashtag;
  ansiPalette = [
    colors.base00
    colors.base08
    colors.base0B
    colors.base0A
    colors.base0D
    colors.base0E
    colors.base0C
    colors.base05
    colors.base03
    colors.base08
    colors.base0B
    colors.base0A
    colors.base0D
    colors.base0E
    colors.base0C
    colors.base07
  ];
  tmuxPalette = lib.concatStringsSep "\n" (
    (lib.imap0 (index: color: "set -gw 'pane-colours[${toString index}]' '${color}'") ansiPalette)
    ++ (map (index: "set -gw 'pane-colours[${toString index}]' colour${toString index}") (
      lib.range 16 255
    ))
  );
  windowBinding =
    n:
    let
      index = toString n;
    in
    ''
      bind -n M-${index} if-shell "${pkgs.tmux}/bin/tmux -S '#{socket_path}' has-session -t '#{session_id}:${index}' 2>/dev/null" "select-window -t :${index}" "new-window -t :${index} -c '#{pane_current_path}'"
    '';
  aliases = {
    ".." = "cd ..";
    "..." = "cd ../..";
    "...." = "cd ../../..";
    "....." = "cd ../../../..";
    # Opt-in full-access launches; plain CLI names remain available for subcommands.
    cx = "codex --yolo";
    hd = "herdr";
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
    autosuggestion = {
      enable = true;
      highlight = "fg=${colors.base03}";
    };
    syntaxHighlighting.enable = true;
    # Atuin keeps Ctrl-R; arrows search only commands matching the typed text.
    historySubstringSearch.enable = true;
    # Start tmux before loading the heavier interactive hooks in the outer shell.
    # Keep SSH, non-Ghostty shells, tmux panes, and plain terminals unattached.
    initContent = lib.mkOrder 500 ''
      if [[ -o interactive && -z ''${TMUX-} && -z ''${SSH_CONNECTION-} \
        && ''${GHOSTTY_NO_TMUX-} != 1 && ''${TERM-} == xterm-ghostty ]] \
        && command -v tmux >/dev/null 2>&1; then
        tmux new-session -A -s main
      fi

      # Use a selectable, case-insensitive completion menu without another
      # completion framework or a second compinit.
      zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'
      zstyle ':completion:*' menu select
      zstyle ':completion:*' group-name ""
      zstyle ':completion:*:descriptions' format '%F{yellow}%d%f'
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
      # A quiet second line keeps long paths and Git details off the input line.
      format = "[╭─](fg:base03)$username$hostname$directory$git_branch$git_status$git_state$nix_shell$nodejs$python$rust$cmd_duration$jobs$status$line_break[╰─](fg:base03)$character";
      directory = {
        format = "[ $path ]($style)";
        style = "bold fg:base00 bg:blue";
        truncation_length = 3;
      };
      username.format = "[$user]($style)";
      hostname = {
        ssh_only = true;
        format = "[@$hostname]($style) ";
      };
      git_branch = {
        format = "[ ⎇ $branch]($style)";
        style = "bold purple";
        truncation_length = 20;
        truncation_symbol = "…";
      };
      git_status = {
        format = "([ $all_status$ahead_behind]($style))";
        style = "bold yellow";
      };
      git_state = {
        format = "[ $state( $progress_current/$progress_total)]($style)";
        style = "bold orange";
      };
      nix_shell = {
        format = "[ nix:$state]($style)";
        style = "bold cyan";
      };
      nodejs = {
        format = "[ node:$version]($style)";
        style = "green";
      };
      python = {
        format = "[ py:$version]($style)";
        style = "yellow";
      };
      rust = {
        format = "[ rs:$version]($style)";
        style = "orange";
      };
      cmd_duration = {
        min_time = 2000;
        format = "[ took $duration]($style)";
        style = "base04";
      };
      jobs = {
        format = "[ bg:$number]($style)";
        number_threshold = 1;
        style = "cyan";
      };
      status = {
        disabled = false;
        format = "[ exit:$status]($style)";
        style = "bold red";
      };
      character = {
        success_symbol = "[❯](bold green) ";
        error_symbol = "[❯](bold red) ";
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
    # Herdr needs FocusOut to alert when its active tab is hidden by outer tmux.
    # The palette responses below keep nested focus-triggered queries safe.
    focusEvents = true;
    # Use Shift-drag for Ghostty text selection while tmux handles the mouse.
    mouse = true;
    extraConfig = ''
      # Answer palette queries inside tmux, so nested TUIs cannot receive
      # fragmented OSC 4 replies from the outer terminal as typed text.
      ${tmuxPalette}
      # Preserve modified Enter keys for apps running through tmux (such as Pi).
      set -g extended-keys on
      set -g extended-keys-format csi-u
      set -g renumber-windows on
      set -g status-interval 10
      set -g status-style 'fg=${colors.base05},bg=${colors.base01}'
      set -g status-left-length 20
      set -g status-left '#[fg=${colors.base0C},bold] ● #S #[fg=${colors.base03},nobold]│ '
      set -g status-right-length 28
      set -g status-right '#[fg=${colors.base0A},bold]#{?pane_in_mode,COPY ,}#[fg=${colors.base0C}]#{b:pane_current_path} #[fg=${colors.base03}]│ #[fg=${colors.base05}]%H:%M '
      set -g window-status-style 'fg=${colors.base04},bg=${colors.base01}'
      set -g window-status-current-style 'fg=${colors.base0A},bg=${colors.base01},bold'
      set -g window-status-separator '#[fg=${colors.base03}] │ #[default]'
      set -g window-status-format ' #I:#W#{window_flags} '
      set -g window-status-current-format ' #I:#W#{window_flags} '
      set -g pane-border-style 'fg=${colors.base02}'
      set -g pane-active-border-style 'fg=${colors.base0D}'
      set -g message-style 'fg=${colors.base00},bg=${colors.base0A}'
      set -g mode-style 'fg=${colors.base00},bg=${colors.base0D}'
      bind c new-window -c "#{pane_current_path}"
      bind '"' split-window -v -c "#{pane_current_path}"
      bind % split-window -h -c "#{pane_current_path}"
      bind -r h select-pane -L
      bind -r j select-pane -D
      bind -r k select-pane -U
      bind -r l select-pane -R
      bind -r H resize-pane -L 5
      bind -r J resize-pane -D 5
      bind -r K resize-pane -U 5
      bind -r L resize-pane -R 5
      # Alt+digits switch to a window or create it in the current directory.
      ${lib.concatMapStringsSep "\n" windowBinding (lib.range 1 9)}
      bind -n M-t new-window -c "#{pane_current_path}"
      bind -n M-n next-window
      bind -n M-p previous-window
      bind -n M-q confirm-before -p 'Close window #I:#W? (y/n)' kill-window
      bind -n M-h select-pane -L
      bind -n M-j select-pane -D
      bind -n M-k select-pane -U
      bind -n M-l select-pane -R
      # Keep tmux mouse selection and keyboard copy mode in the Wayland clipboard.
      bind -T copy-mode MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel '${pkgs.wl-clipboard}/bin/wl-copy'
      bind -T copy-mode M-w send-keys -X copy-pipe-and-cancel '${pkgs.wl-clipboard}/bin/wl-copy'
      bind -T copy-mode C-w send-keys -X copy-pipe-and-cancel '${pkgs.wl-clipboard}/bin/wl-copy'
      bind -T copy-mode WheelUpPane select-pane \; send-keys -X -N 3 scroll-up
      bind -T copy-mode WheelDownPane select-pane \; send-keys -X -N 3 scroll-down
      bind r source-file ~/.config/tmux/tmux.conf \; display-message 'tmux config reloaded'
    '';
  };
}
