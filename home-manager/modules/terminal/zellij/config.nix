# Zellij settings and keybinds.

{ config, pkgs, ... }:

let
  zellijAiPanel = pkgs.writeShellScriptBin "zellij-ai-panel" ''
    set -euo pipefail

    if [[ -z "''${ZELLIJ:-}" ]]; then
      echo "zellij-ai-panel must be run inside Zellij" >&2
      exit 1
    fi

    zellij=${pkgs.zellij}/bin/zellij
    zsh=${pkgs.zsh}/bin/zsh
    fzf=${pkgs.fzf}/bin/fzf

    choice="$(
      printf '%s\n' \
        "Claude Code" \
        "Claude GLM" \
        "OpenCode" \
        "OpenCode GPT" \
        "OpenCode Sonnet" \
        "OpenCode Gemini" \
        "OpenCode OpenRouter" \
        "Codex High" \
        "Codex XHigh" \
        "Gemini" \
        "oh-my-pi GLM" \
        "AI Council" \
        "AI Logs" \
        "Agent Inventory" \
      | "$fzf" \
          --prompt='agent > ' \
          --height=45% \
          --layout=reverse \
          --border \
          --cycle
    )" || exit 0

    case "$choice" in
      "Claude Code")
        exec "$zellij" action new-tab --name "󰚩 cl" -- "$zsh" -ic "cl"
        ;;
      "Claude GLM")
        exec "$zellij" action new-tab --name "󰚩 clglm" -- "$zsh" -ic "clglm"
        ;;
      "OpenCode")
        exec "$zellij" action new-tab --name " oc" -- "$zsh" -ic "oc"
        ;;
      "OpenCode GPT")
        exec "$zellij" action new-tab --name " ocgpt" -- "$zsh" -ic "ocgpt"
        ;;
      "OpenCode Sonnet")
        exec "$zellij" action new-tab --name " ocs" -- "$zsh" -ic "ocs"
        ;;
      "OpenCode Gemini")
        exec "$zellij" action new-tab --name " ocgem" -- "$zsh" -ic "ocgem"
        ;;
      "OpenCode OpenRouter")
        exec "$zellij" action new-tab --name " ocor" -- "$zsh" -ic "ocor"
        ;;
      "Codex High")
        exec "$zellij" action new-tab --name "󱚤 hcx" -- "$zsh" -ic "hcx"
        ;;
      "Codex XHigh")
        exec "$zellij" action new-tab --name "󱚤 xcx" -- "$zsh" -ic "xcx"
        ;;
      "Gemini")
        exec "$zellij" action new-tab --name "󰊭 gem" -- "$zsh" -ic "gem"
        ;;
      "oh-my-pi GLM")
        exec "$zellij" action new-tab --name "󰐻 opi" -- "$zsh" -ic "opi"
        ;;
      "AI Council")
        exec "$zellij" action new-tab --name "󰚩 council" --layout "$HOME/.config/zellij/layouts/ai-council.kdl"
        ;;
      "AI Logs")
        exec "$zellij" action new-tab --name "󰙨 ai-logs" --layout "$HOME/.config/zellij/layouts/ai-observe.kdl"
        ;;
      "Agent Inventory")
        exec "$zellij" action new-tab --name "󰒋 agents" -- "$zsh" -ic "ai-agent-inventory; exec zsh"
        ;;
    esac
  '';

  scrollSearchSharedBinds = ''
    bind "Esc" "q" { ScrollToBottom; SwitchToMode "Normal"; }
    bind "Ctrl c" { ScrollToBottom; SwitchToMode "Normal"; }
    bind "j" "Down" { ScrollDown; }
    bind "k" "Up" { ScrollUp; }
    bind "d" "Ctrl d" { HalfPageScrollDown; }
    bind "u" "Ctrl u" { HalfPageScrollUp; }
    bind "Ctrl f" "PageDown" { PageScrollDown; }
    bind "Ctrl b" "PageUp" { PageScrollUp; }
  '';
in

{
  home.packages = [ zellijAiPanel ];

  programs.zellij = {
    enable = true;
    # HM's zellij attach -c breaks with multiple sessions; auto-start is in zsh initContent
    enableZshIntegration = false;

    settings = {
      theme = "default"; # Stylix generates ~/.config/zellij/themes/stylix.kdl defining "default"
      default_shell = "${pkgs.zsh}/bin/zsh";
      default_layout = "default";
      default_mode = "normal";
      layout_dir = "${config.home.homeDirectory}/.config/zellij/layouts";
      theme_dir = "${config.home.homeDirectory}/.config/zellij/themes";

      pane_frames = false;
      simplified_ui = false;
      styled_underlines = true;
      auto_layout = true;
      mouse_mode = true;
      advanced_mouse_actions = true;
      focus_follows_mouse = true;
      visual_bell = true;

      copy_command = "${pkgs.wl-clipboard}/bin/wl-copy";
      copy_clipboard = "system";
      copy_on_select = true;

      scroll_buffer_size = 50000;
      scrollback_editor = "${pkgs.neovim}/bin/nvim";

      session_serialization = true;
      pane_viewport_serialization = true;
      scrollback_lines_to_serialize = 10000;
      serialization_interval = 120;

      on_force_close = "quit";
      show_startup_tips = false;
      show_release_notes = false;
      stacked_resize = true;
      web_sharing = "disabled";
    };

    extraConfig = ''
      load_plugins {
        "file:~/.config/zellij/plugins/zellij-attention.wasm"
      }

      ui {
        pane_frames {
          rounded_corners true
          hide_session_name true
        }
      }

      keybinds {
        unbind "Ctrl q"

        scroll {
          ${scrollSearchSharedBinds}
          bind "g" { ScrollToTop; }
          bind "G" { ScrollToBottom; }
          bind "e" { EditScrollback; SwitchToMode "Normal"; }
          bind "/" "s" { SwitchToMode "EnterSearch"; SearchInput 0; }
        }

        search {
          ${scrollSearchSharedBinds}
          bind "n" { Search "down"; }
          bind "N" { Search "up"; }
          bind "c" { SearchToggleOption "CaseSensitivity"; }
          bind "w" { SearchToggleOption "Wrap"; }
          bind "o" { SearchToggleOption "WholeWord"; }
        }

        entersearch {
          bind "Ctrl c" "Esc" { SwitchToMode "Scroll"; }
          bind "Enter" { SwitchToMode "Search"; }
        }

        session {
          bind "Ctrl o" "Esc" { SwitchToMode "Normal"; }
          bind "d" { Detach; }
        }

        shared_except "scroll" "locked" "entersearch" "search" {
          bind "Ctrl s" { SwitchToMode "Scroll"; }
        }

        shared_except "locked" "renametab" "renamepane" "entersearch" {
          bind "Alt h" { MoveFocusOrTab "Left"; }
          bind "Alt j" { MoveFocus "Down"; }
          bind "Alt k" { MoveFocus "Up"; }
          bind "Alt l" { MoveFocusOrTab "Right"; }

          bind "Alt 1" { GoToTab 1; SwitchToMode "Normal"; }
          bind "Alt 2" { GoToTab 2; SwitchToMode "Normal"; }
          bind "Alt 3" { GoToTab 3; SwitchToMode "Normal"; }
          bind "Alt 4" { GoToTab 4; SwitchToMode "Normal"; }
          bind "Alt 5" { GoToTab 5; SwitchToMode "Normal"; }
          bind "Alt 6" { GoToTab 6; SwitchToMode "Normal"; }
          bind "Alt 7" { GoToTab 7; SwitchToMode "Normal"; }
          bind "Alt 8" { GoToTab 8; SwitchToMode "Normal"; }
          bind "Alt 9" { GoToTab 9; SwitchToMode "Normal"; }

          bind "Alt n" { NewPane; }
          bind "Alt s" { NewPane "Down"; SwitchToMode "Normal"; }
          bind "Alt v" { NewPane "Right"; SwitchToMode "Normal"; }
          bind "Alt S" { NewPane "stacked"; SwitchToMode "Normal"; }
          bind "Alt x" { CloseFocus; SwitchToMode "Normal"; }
          bind "Alt z" { ToggleFocusFullscreen; SwitchToMode "Normal"; }
          bind "Alt w" { ToggleFloatingPanes; SwitchToMode "Normal"; }
          bind "Alt f" { TogglePaneEmbedOrFloating; SwitchToMode "Normal"; }

          bind "Alt Enter" { NewTab; SwitchToMode "Normal"; }
          bind "Alt q" { CloseTab; SwitchToMode "Normal"; }
          bind "Alt 0" { ToggleTab; }
          bind "Alt ." { MoveTab "Right"; }
          bind "Alt ," { MoveTab "Left"; }

          bind "Alt =" { Resize "Increase"; }
          bind "Alt -" { Resize "Decrease"; }

          bind "Alt [" { PreviousSwapLayout; }
          bind "Alt ]" { NextSwapLayout; }

          bind "Alt e" { EditScrollback; SwitchToMode "Normal"; }
          bind "Alt a" {
            Run "${zellijAiPanel}/bin/zellij-ai-panel" {
              floating true
              width "60%"
              height "50%"
              close_on_exit true
            }
          }
          bind "Alt A" {
            NewTab {
              name "󰚩 council"
              layout "${config.home.homeDirectory}/.config/zellij/layouts/ai-council.kdl"
            }
            SwitchToMode "Normal";
          }
          bind "Alt L" {
            NewTab {
              name "󰙨 ai-logs"
              layout "${config.home.homeDirectory}/.config/zellij/layouts/ai-observe.kdl"
            }
            SwitchToMode "Normal";
          }

          bind "Alt o" {
            LaunchOrFocusPlugin "zellij:session-manager" {
              floating true
              move_to_focused_tab true
            }
          }
          bind "Alt O" {
            LaunchOrFocusPlugin "zellij:layout-manager" {
              floating true
              move_to_focused_tab true
            }
          }
          bind "Alt P" {
            LaunchOrFocusPlugin "zellij:plugin-manager" {
              floating true
              move_to_focused_tab true
            }
          }
          bind "Alt C" {
            LaunchOrFocusPlugin "configuration" {
              floating true
              move_to_focused_tab true
            }
          }

          bind "Alt p" {
            LaunchOrFocusPlugin "file:~/.config/zellij/plugins/monocle.wasm" {
              floating true
            }
          }
          bind "Alt r" {
            LaunchOrFocusPlugin "file:~/.config/zellij/plugins/room.wasm" {
              floating true
              ignore_case true
            }
          }
          bind "Alt b" {
            LaunchOrFocusPlugin "file:~/.config/zellij/plugins/harpoon.wasm" {
              floating true
            }
          }
          bind "Alt /" {
            LaunchOrFocusPlugin "file:~/.config/zellij/plugins/zellij-forgot.wasm" {
              floating true
              "LOAD_ZELLIJ_BINDINGS" "true"
            }
          }
          bind "Alt m" {
            LaunchPlugin "file:~/.config/zellij/plugins/multitask.wasm" {
              floating false
            }
          }
        }
      }
    '';
  };
}
