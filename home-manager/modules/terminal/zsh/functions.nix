# Zsh initContent: shell functions, environment setup, and sops-enabled agent wrappers.

{
  config,
  constants,
  lib,
  secretLoader,
  ...
}:

let
  inherit (secretLoader) loadSecretFn;
  aiShellEnv = config.programs.aiAgents.shellEnv;

  # Profiles that get a simple wrapper (excludes default "opencode" and
  # "opencode-openrouter" which needs secret loading).
  simpleWrapperProfiles = builtins.filter (
    p: p.alias != "oc" && p.name != "opencode-openrouter"
  ) aiShellEnv.opencodeProfileData;

  profileSuffix = p: builtins.replaceStrings [ "opencode-" ] [ "" ] p.name;
in

{
  programs.zsh.initContent = ''
    # === LS_COLORS ===
    # Vivid LS_COLORS (cached)
    if command -v vivid >/dev/null 2>&1; then
      ls_colors_cache="$HOME/.cache/vivid-ls-colors"
      if [[ ! -f "$ls_colors_cache" ]]; then
        mkdir -p "$HOME/.cache"
        vivid generate ${constants.theme} > "$ls_colors_cache"
      fi
      export LS_COLORS="$(cat "$ls_colors_cache")"
    fi

    # === Sops secret loading ===
    ${loadSecretFn}

    _load_zai_key() { _load_secret zai_api_key; }
    _load_openrouter_key() { _load_secret openrouter_api_key; }

    # Export Z.AI key for omp models.yml resolution (non-fatal)
    if _zai_key_export="$(_load_zai_key 2>/dev/null)" && [[ -n "$_zai_key_export" ]]; then
      export ZAI_API_KEY="$_zai_key_export"
    fi

    # === AI agent wrappers ===
    _ai_tab_icon() {
      if [[ -n "''${ZELLIJ_MOBILE:-}" ]]; then
        return 0
      fi

      case "$1" in
        cl*|ocl*|hcl*) printf '\uf1b0 ' ;;                   #  Claude — cl, clu, clglm, ocl, hcl + all workflow suffixes
        oc*|locgpt*|mocgpt*|xocgpt*) printf '\ue7a4 ' ;;     #  OpenCode — oc, ocglm, ocgem, ocgpt, ocs, oczen + all workflow suffixes
        cx*|lcx*|mcx*|hcx*|xcx*) printf '\uf1c0 ' ;;         #  Codex — cx, lcx, mcx, hcx, xcx + all workflow suffixes
        opi*) printf '\uf135 ' ;;                              #  oh-my-pi — opi + all workflow suffixes
        gem*) printf '\uf529 ' ;;                              #  Gemini — gem + all workflow suffixes
        *) ;;
      esac
    }

    _zellij_rename_tab() {
      local tab_name="$1"
      [[ -n "$tab_name" && -n "${"ZELLIJ:-"}" ]] || return 0
      local icon
      icon="$(_ai_tab_icon "$tab_name")"
      command zellij action rename-tab "''${icon}''${tab_name}" >/dev/null 2>&1 || true
    }

    _ai_agent_exec() {
      local tab_name="$1"
      shift
      if [[ "$1" == "--" ]]; then
        shift
      fi
      _zellij_rename_tab "$tab_name"
      # Inject --debug-file for Claude Code sessions
      if [[ "$1" == "claude" ]]; then
        local debug_dir="''${AI_AGENT_LOG_DIR:-$HOME/.local/share/ai-agents/logs}"
        mkdir -p "$debug_dir"
        set -- "$@" "--debug-file" "$debug_dir/claude-debug-$(date +%Y-%m-%d).log"
      fi
      "$@"
    }

    claude_glm() {
      local key; key="$(_load_zai_key)" || return 1
      _zellij_rename_tab "clglm"
      local debug_dir="''${AI_AGENT_LOG_DIR:-$HOME/.local/share/ai-agents/logs}"
      mkdir -p "$debug_dir"
      ANTHROPIC_AUTH_TOKEN="$key" \
      ${aiShellEnv.zaiInlinePrefix} \
      claude --dangerously-skip-permissions --debug-file "$debug_dir/claude-debug-$(date +%Y-%m-%d).log" "$@"
    }

    omp_glm() {
      local key; key="$(_load_zai_key)" || return 1
      _zellij_rename_tab "opi"
      ZAI_API_KEY="$key" omp "$@"
    }

    _opencode_profile() {
      local profile="$1"
      local tab_name="$2"
      shift 2
      _zellij_rename_tab "$tab_name"
      OPENCODE_CONFIG_DIR="$HOME/.config/opencode-$profile" opencode --log-level WARN "$@"
    }

    ${lib.concatStringsSep "\n\n" (
      map (p: ''
        opencode_${profileSuffix p}() {
          _opencode_profile "${profileSuffix p}" "${p.alias}" "$@"
        }
      '') simpleWrapperProfiles
    )}

    opencode_openrouter() {
      local key; key="$(_load_openrouter_key)" || return 1
      OPENROUTER_API_KEY="$key" _opencode_profile "openrouter" "ocor" "$@"
    }

    za() {
      if [[ -n "''${ZELLIJ:-}" ]]; then
        zellij-ai-panel "$@"
      else
        zellij --layout ai
      fi
    }

    zac() {
      if [[ -n "''${ZELLIJ:-}" ]]; then
        if [[ -n "''${ZELLIJ_MOBILE:-}" ]]; then
          zellij action new-tab --name "council" --layout "$HOME/.config/zellij/layouts/ai-council.kdl"
        else
          zellij action new-tab --name "󰚩 council" --layout "$HOME/.config/zellij/layouts/ai-council.kdl"
        fi
      else
        zellij --layout ai-council
      fi
    }

    zalogs() {
      if [[ -n "''${ZELLIJ:-}" ]]; then
        if [[ -n "''${ZELLIJ_MOBILE:-}" ]]; then
          zellij action new-tab --name "ai-logs" --layout "$HOME/.config/zellij/layouts/ai-observe.kdl"
        else
          zellij action new-tab --name "󰙨 ai-logs" --layout "$HOME/.config/zellij/layouts/ai-observe.kdl"
        fi
      else
        zellij --layout ai-observe
      fi
    }

    zm() {
      zellij-mobile "$@"
    }

    zp() {
      if [[ -n "''${ZELLIJ:-}" ]]; then
        zellij action new-pane "$@"
      else
        echo "zp must be run inside Zellij" >&2
        return 1
      fi
    }

    zpr() {
      if [[ -n "''${ZELLIJ:-}" ]]; then
        zellij action new-pane --direction right "$@"
      else
        echo "zpr must be run inside Zellij" >&2
        return 1
      fi
    }

    zpd() {
      if [[ -n "''${ZELLIJ:-}" ]]; then
        zellij action new-pane --direction down "$@"
      else
        echo "zpd must be run inside Zellij" >&2
        return 1
      fi
    }

    # === AI multi-pane launcher ===
    # Launch multiple AI agents side-by-side in Zellij panes
    # Prompt injection: claude/codex/gemini use positional, opencode uses --prompt
    aip() {
      if [[ $# -eq 0 ]]; then
        echo "Usage: aip <agent> [agent...] [\"prompt\"]" >&2
        echo "  Any alias or function: cl, clglm, oc, ocglm, gem, cx..." >&2
        echo "  Last arg becomes the initial prompt if not a known command." >&2
        echo "Examples:" >&2
        echo "  aip oc cl                  # Two agents side-by-side" >&2
        echo "  aip oc clglm gem           # Three agents" >&2
        echo '  aip oc ocglm "who are you" # With prompt injection' >&2
        return 1
      fi

      # Collect args into array for safe manipulation
      local -a agents=("$@")
      local prompt=""

      # Detect prompt: if last arg is not a recognized command, treat as prompt
      if ! type "''${agents[-1]}" &>/dev/null; then
        prompt="''${agents[-1]}"
        agents[-1]=()
      fi

      if [[ ''${#agents[@]} -eq 0 ]]; then
        echo "Error: no agents specified (only a prompt was given)" >&2
        return 1
      fi

      local layout_file zsh_bin
      layout_file=$(mktemp /tmp/aip-XXXXXX.kdl)
      zsh_bin="$SHELL"
      local joined_agents="''${(j:+:)agents}"

      # Escape double quotes for KDL string safety
      local kdl_prompt="''${prompt//\"/\\\"}"

      # Inherit zjstatus bar from default layout
      local default_layout="$HOME/.config/zellij/layouts/default.kdl"
      if [[ -f "$default_layout" ]]; then
        head -n -1 "$default_layout" > "$layout_file"
      else
        echo 'layout {' > "$layout_file"
      fi

      {
        echo "  tab name=\"$joined_agents\" focus=true {"
        echo '    pane split_direction="vertical" {'
        local i=0 cmd
        for agent in "''${agents[@]}"; do
          # Build command with prompt injection per agent family
          if [[ -n "$prompt" ]]; then
            case "$agent" in
              oc|ocglm|ocgem|ocgpt|ocor|ocs|oczen|opi|opencode*|gem*|gemini*)
                cmd="$agent --prompt '$kdl_prompt'" ;;
              *)
                cmd="$agent '$kdl_prompt'" ;;
            esac
          else
            cmd="$agent"
          fi

          if [[ $i -eq 0 ]]; then
            echo "      pane name=\"$agent\" command=\"$zsh_bin\" focus=true {"
          else
            echo "      pane name=\"$agent\" command=\"$zsh_bin\" {"
          fi
          echo "        args \"-ic\" \"$cmd\""
          echo "      }"
          ((i++))
        done
        echo '    }'
        echo '  }'
        echo '}'
      } >> "$layout_file"

      if [[ -n "''${ZELLIJ:-}" ]]; then
        zellij action new-tab --layout "$layout_file"
      else
        zellij --layout "$layout_file"
      fi

      rm -f "$layout_file"
    }

    # === Environment setup ===
    export GPG_TTY=$(tty)

    if [ -f ~/.nix-profile/etc/profile.d/hm-session-vars.sh ]; then
      source ~/.nix-profile/etc/profile.d/hm-session-vars.sh
    fi

    for pydir in ~/.nix-profile/lib/python3.*/site-packages; do
      if [ -d "$pydir" ]; then
        export PYTHONPATH="$pydir:$PYTHONPATH"
        break
      fi
    done
  '';
}
