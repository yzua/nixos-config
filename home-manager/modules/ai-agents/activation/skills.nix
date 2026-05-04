# Skill installation activation script.
# Bootstraps skills CLI, installs configured skills with retry, manages state caching.
# Also mirrors installed skills to all OpenCode profiles.

{
  cfg,
  lib,
  pkgs,
  toJSON,
  opencodeProfileNames,
}:

let
  normalizedSkills = lib.unique cfg.skills;
  repoLevelSkills = builtins.filter builtins.isString normalizedSkills;
  individualSkills = builtins.filter (s: !(builtins.isString s)) normalizedSkills;
  individualSkillsByRepo = builtins.foldl' (
    acc: s:
    acc
    // {
      ${s.repo} = (acc.${s.repo} or [ ]) ++ [ s.skill ];
    }
  ) { } individualSkills;
  desiredSkillStateJson = toJSON normalizedSkills;
  # Pre-generate install commands at Nix eval time
  repoLevelSkillCommands = map (
    repo:
    # Repo-level: skills add "owner/repo" --global --yes
    ''
      processed_groups=$((processed_groups + 1))
      echo "  [$processed_groups/$configured_groups] ${repo}"
      echo "  → ${repo}"
      echo "  [AI] starting install for ${repo} at $(date +'%F %T')"
      total_attempts=$((total_attempts + 1))
      if ! attempt_cmd "install ${repo}" "$SKILLS_BIN" add "${repo}" --global --yes; then
        echo "❌ Failed to install ${repo}"
        failed_installs=$((failed_installs + 1))
      else
        echo "✔ Installed ${repo}"
        successful_installs=$((successful_installs + 1))
      fi
    '') repoLevelSkills;
  individualSkillCommands = lib.mapAttrsToList (
    repo: skills:
    let
      uniqueSkills = lib.unique skills;
      skillFlags = lib.concatMapStringsSep " " (
        skill: "--skill ${lib.escapeShellArg skill}"
      ) uniqueSkills;
      skillList = lib.concatStringsSep ", " uniqueSkills;
    in
    # Batched: skills add https://github.com/owner/repo --skill one --skill two --global --yes
    ''
      processed_groups=$((processed_groups + 1))
      echo "  [$processed_groups/$configured_groups] ${repo} (${toString (builtins.length uniqueSkills)} skill(s))"
      echo "  → ${repo}: ${skillList}"
      echo "  [AI] starting batched install for ${repo} at $(date +'%F %T')"
      total_attempts=$((total_attempts + 1))
      if ! attempt_cmd "install ${repo} (${skillList})" "$SKILLS_BIN" add "https://github.com/${repo}" ${skillFlags} --global --yes; then
        echo "❌ Failed to install ${repo}: ${skillList}"
        failed_installs=$((failed_installs + 1))
      else
        echo "✔ Installed ${repo}: ${skillList}"
        successful_installs=$((successful_installs + 1))
      fi
    ''
  ) individualSkillsByRepo;
  skillCommands = repoLevelSkillCommands ++ individualSkillCommands;
  installGroupCount =
    builtins.length repoLevelSkillCommands + builtins.length individualSkillCommands;
in
lib.mkIf (cfg.skills != [ ]) (
  lib.hm.dag.entryAfter [ "writeBoundary" "createJSWorkspace" ] ''
    export BUN_INSTALL="$HOME/.bun"
    export PATH="${pkgs.git}/bin:${pkgs.nodejs}/bin:${pkgs.bun}/bin:$BUN_INSTALL/bin:$PATH"

    SKILLS_BIN="$BUN_INSTALL/bin/skills"
    if [[ ! -x "$SKILLS_BIN" ]]; then
      SKILLS_BIN="$(command -v skills 2>/dev/null || true)"
    fi

    if [[ -z "$SKILLS_BIN" ]]; then
      echo "📦 skills CLI missing, bootstrapping with bun..."
      if ! $DRY_RUN_CMD "${pkgs.bun}/bin/bun" add --global --cwd "$HOME" --no-summary skills; then
        echo "❌ Failed to bootstrap skills CLI"
        exit 1
      fi

      SKILLS_BIN="$BUN_INSTALL/bin/skills"
      if [[ ! -x "$SKILLS_BIN" ]]; then
        SKILLS_BIN="$(command -v skills 2>/dev/null || true)"
      fi
    fi

    if [[ -z "$SKILLS_BIN" ]]; then
      echo "❌ skills CLI not found after bootstrap"
      exit 1
    fi

    if ! command -v git >/dev/null 2>&1; then
      echo "❌ git is required for skills installation but is not in PATH"
      exit 1
    fi

    desired_skill_state_json=${lib.escapeShellArg desiredSkillStateJson}
    # Include a version marker so cache invalidates when install flags change
    desired_skill_state_hash=$(printf '%s:v4' "$desired_skill_state_json" | ${pkgs.coreutils}/bin/sha256sum | cut -d' ' -f1)
    skill_state_cache_dir="$HOME/.cache/ai-agents"
    skill_state_cache_file="$skill_state_cache_dir/skills-state.sha256"
    skill_lock_file="$HOME/.agents/.skill-lock.json"
    skip_skill_install=0

    if [[ -f "$skill_state_cache_file" ]] && [[ -f "$skill_lock_file" ]]; then
      current_skill_state_hash="$(cat "$skill_state_cache_file")"
      if [[ "$current_skill_state_hash" == "$desired_skill_state_hash" ]]; then
        echo "✓ Skills configuration unchanged; skipping reinstall"
        skip_skill_install=1
      fi
    fi

    if [[ "$skip_skill_install" -eq 0 ]]; then
      # Remove all existing global skills before reinstall to prevent stale accumulation
      echo "🧹 Removing all existing global skills before reinstall..."
      "$SKILLS_BIN" remove --global --all --yes 2>/dev/null || true
      # Clean all skill storage locations (skills.sh stores in ~/.agents/skills/,
      # symlinks into ~/.claude/skills/; OpenCode reads from both)
      rm -rf "$HOME/.agents/skills"/* 2>/dev/null || true
      rm -rf "$HOME/.agents/.skill-lock.json" 2>/dev/null || true
      rm -rf "$HOME/.claude/skills"/* 2>/dev/null || true
      echo "✓ Cleaned skill directories"

      attempt_cmd() {
        local label="$1"
        shift
        local attempt
        for attempt in 1 2 3; do
          if $DRY_RUN_CMD "$@"; then
            return 0
          fi
          echo "⚠ $label failed (attempt $attempt/3)"
          sleep 1
        done
        return 1
      }

      failed_installs=0
      successful_installs=0
      skipped_installs=0
      total_attempts=0
      processed_groups=0
      configured_entries=${toString (builtins.length normalizedSkills)}
      configured_groups=${toString installGroupCount}
      install_started_epoch=$(date +%s)
      echo "📦 Installing agent skills from skills.sh ($configured_entries configured entries, $configured_groups repo batch(es))..."
      echo "ℹ Running repo batches sequentially to avoid skills lock contention in global state"
      ${lib.concatStringsSep "" skillCommands}

      install_duration_seconds=$(( $(date +%s) - install_started_epoch ))

      echo "🧠 Skills summary: configured=$configured_entries batches=$processed_groups attempted=$total_attempts success=$successful_installs skipped=$skipped_installs failures=$failed_installs duration=''${install_duration_seconds}s"

      if [[ "$failed_installs" -gt 0 ]]; then
        echo "⚠ Skills installation finished with $failed_installs failures"
        echo "⚠ Continuing Home Manager activation; agent skills sync is best-effort"
      fi

      mkdir -p "$skill_state_cache_dir"
      printf '%s' "$desired_skill_state_hash" > "$skill_state_cache_file"

      echo "✓ Skills installation complete"
    fi

    # Mirror Claude skills to all OpenCode profiles.
    # skills.sh only installs to the default opencode profile,
    # so we symlink from ~/.claude/skills into every profile's skills dir.
    if [[ -d "$HOME/.claude/skills" ]]; then
      for profile in ${lib.concatStringsSep " " (map lib.escapeShellArg opencodeProfileNames)}; do
        profile_skills="$HOME/.config/$profile/skills"
        mkdir -p "$profile_skills"
        # Remove stale dead symlinks first
        find "$profile_skills" -maxdepth 1 -type l ! -exec test -e {} \; -delete 2>/dev/null || true
        shopt -s nullglob
        for skill_dir in "$HOME/.claude/skills"/*; do
          [[ -d "$skill_dir" ]] || continue
          skill_name="$(basename "$skill_dir")"
          link="$profile_skills/$skill_name"
          if [[ ! -e "$link" ]]; then
            ln -sfn "$skill_dir" "$link"
          fi
        done
        shopt -u nullglob
      done
      echo "✓ Mirrored skills to ${toString (builtins.length opencodeProfileNames)} OpenCode profiles"
    fi
  ''
)
