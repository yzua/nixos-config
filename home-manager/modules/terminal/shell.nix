# Shared Bash/Zsh tools, local history, prompt, and Ghostty auto-attachment.

{
  config,
  lib,
  ...
}:

let
  colors = config.lib.stylix.colors.withHashtag;
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
}
