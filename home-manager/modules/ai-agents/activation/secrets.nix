# Secret patching activation — injects API keys and tokens into agent configs.

{
  cfg,
  pkgs,
  lib,
  opencodeConfigPathList,
  opencodeZaiFilter,
  claudeZaiFilter,
  ompZaiFilter,
  geminiZaiFilter,
  githubPlaceholderFilter,
  openrouterPlaceholderFilter,
  context7PlaceholderFilter,
}:
lib.hm.dag.entryAfter [ "writeBoundary" "linkGeneration" "setupCodexConfig" "setupClaudeConfig" ] ''
  patch_json_file() {
    local file="$1"
    local arg_name="$2"
    local arg_value="$3"
    local filter="$4"

    ${pkgs.jq}/bin/jq --arg "$arg_name" "$arg_value" "$filter" "$file" > "$file.tmp" && mv "$file.tmp" "$file"
  }

  escape_sed_replacement() {
    printf '%s\n' "$1" | ${pkgs.gnused}/bin/sed 's/[&/\]/\\&/g'
  }

  # Patch a secret value into all agent config files.
  # Args: secret jq_arg_name opencode_filter [claude_filter] [gemini_filter] [toml_placeholder] [toml_append_section] [label]
  patch_secret_to_all_configs() {
    local secret="$1" jq_arg="$2" opencode_filter="$3"
    local claude_filter="''${4:-}" gemini_filter="''${5:-}"
    local toml_placeholder="''${6:-}" toml_append="''${7:-}" label="''${8:-}"

    for OPENCODE_CFG in ${opencodeConfigPathList}; do
      if [[ -f "$OPENCODE_CFG" ]]; then
        patch_json_file "$OPENCODE_CFG" "$jq_arg" "$secret" "$opencode_filter"
        echo "✓ Patched $(basename "$(dirname "$OPENCODE_CFG")")/opencode.json with $label"
      fi
    done

    if [[ -n "$claude_filter" ]] && [[ -f "$HOME/.mcp.json" ]]; then
      patch_json_file "$HOME/.mcp.json" "$jq_arg" "$secret" "$claude_filter"
      echo "✓ Patched .mcp.json with $label"
    fi

    if [[ -n "$toml_placeholder" ]] && [[ -f "$HOME/.codex/config.toml" ]]; then
      local escaped
      escaped="$(escape_sed_replacement "$secret")"
      ${pkgs.gnused}/bin/sed -i "s/$toml_placeholder/$escaped/g" "$HOME/.codex/config.toml"
      if [[ -n "$toml_append" ]] && grep -q "$toml_append" "$HOME/.codex/config.toml"; then
        ${pkgs.gnused}/bin/sed -i "/$toml_append/a Z_AI_API_KEY = \"$escaped\"" "$HOME/.codex/config.toml"
      fi
      echo "✓ Patched codex config.toml with $label"
    fi

    if ${lib.boolToString cfg.gemini.enable} && [[ -n "$gemini_filter" ]] && [[ -f "$HOME/.gemini/settings.json" ]]; then
      patch_json_file "$HOME/.gemini/settings.json" "$jq_arg" "$secret" "$gemini_filter"
      echo "✓ Patched gemini settings.json with $label"
    fi
  }

  # --- Z.AI ---
  if [[ -n "${cfg.secrets.zaiApiKeyFile or ""}" ]]; then
    if [[ -f "${cfg.secrets.zaiApiKeyFile}" ]]; then
      ZAI_KEY="$(cat "${cfg.secrets.zaiApiKeyFile}")"
      patch_secret_to_all_configs \
        "$ZAI_KEY" key \
        ${lib.escapeShellArg opencodeZaiFilter} \
        ${lib.escapeShellArg claudeZaiFilter} \
        ${lib.escapeShellArg geminiZaiFilter} \
        "__ZAI_API_KEY_PLACEHOLDER__" \
        '\[mcp_servers.zai-mcp-server.env\]' \
        "Z.AI API key + remote MCPs"
      if [[ -f "$HOME/.omp/agent/mcp.json" ]]; then
        patch_json_file "$HOME/.omp/agent/mcp.json" key "$ZAI_KEY" ${lib.escapeShellArg ompZaiFilter}
        echo "✓ Patched .omp/agent/mcp.json with Z.AI API key + remote MCPs"
      fi
      unset ZAI_KEY
    else
      echo "⚠ ${cfg.secrets.zaiApiKeyFile} not found - run 'just nixos' first"
    fi
  fi

  # --- OpenRouter ---
  if [[ -n "${cfg.secrets.openrouterApiKeyFile or ""}" ]]; then
    if [[ -f "${cfg.secrets.openrouterApiKeyFile}" ]]; then
      OPENROUTER_KEY="$(cat "${cfg.secrets.openrouterApiKeyFile}")"
      patch_secret_to_all_configs \
        "$OPENROUTER_KEY" key \
        ${lib.escapeShellArg openrouterPlaceholderFilter} \
        "" "" "" "" \
        "OpenRouter API key"
      unset OPENROUTER_KEY
    else
      echo "⚠ ${cfg.secrets.openrouterApiKeyFile} not found - run 'just nixos' first"
    fi
  fi

  # --- Context7 ---
  if [[ -n "${cfg.secrets.context7ApiKeyFile or ""}" ]]; then
    if [[ -f "${cfg.secrets.context7ApiKeyFile}" ]]; then
      CONTEXT7_KEY="$(cat "${cfg.secrets.context7ApiKeyFile}")"
      patch_secret_to_all_configs \
        "$CONTEXT7_KEY" key \
        ${lib.escapeShellArg context7PlaceholderFilter} \
        ${lib.escapeShellArg context7PlaceholderFilter} \
        ${lib.escapeShellArg context7PlaceholderFilter} \
        "__CONTEXT7_API_KEY_PLACEHOLDER__" \
        "" \
        "Context7 API key"
      if [[ -f "$HOME/.omp/agent/mcp.json" ]]; then
        patch_json_file "$HOME/.omp/agent/mcp.json" key "$CONTEXT7_KEY" ${lib.escapeShellArg context7PlaceholderFilter}
        echo "✓ Patched .omp/agent/mcp.json with Context7 API key"
      fi
      unset CONTEXT7_KEY
    else
      echo "⚠ ${cfg.secrets.context7ApiKeyFile} not found - run 'just nixos' first"
    fi
  fi

  # --- GitHub (from gh CLI) ---
  if ${pkgs.gh}/bin/gh auth status &> /dev/null; then
    GH_TOKEN="$(${pkgs.gh}/bin/gh auth token)"
    patch_secret_to_all_configs \
      "$GH_TOKEN" token \
      ${lib.escapeShellArg githubPlaceholderFilter} \
      ${lib.escapeShellArg githubPlaceholderFilter} \
      ${lib.escapeShellArg githubPlaceholderFilter} \
      "__GITHUB_TOKEN_PLACEHOLDER__" \
      "" \
      "GitHub token from gh CLI"
    if [[ -f "$HOME/.omp/agent/mcp.json" ]]; then
      patch_json_file "$HOME/.omp/agent/mcp.json" token "$GH_TOKEN" ${lib.escapeShellArg githubPlaceholderFilter}
      echo "✓ Patched .omp/agent/mcp.json with GitHub token"
    fi
    unset GH_TOKEN
  else
    echo "⚠ gh CLI not authenticated - GitHub MCP will not work (run 'gh auth login')"
  fi

''
