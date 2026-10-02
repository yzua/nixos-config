#!/usr/bin/env bash
# Own selected-generation facts, preview publication, status, and guarded activation.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/config.sh
source scripts/saved-preview-build.sh

# Keep output mappings and owner prerequisites private to the workflow commands.
select_generation() {
  generation_kind="$1"
  case "$generation_kind" in
  system)
    select_system
    generation_name="$NIXOS_CONFIG"
    generation_ref="$system_ref"
    generation_build="$system_ref.config.system.build.toplevel"
    generation_active=/run/current-system
    generation_preview=preview
    generation_label="NixOS ($NIXOS_CONFIG)"
    ;;
  home)
    select_home
    require_home_owner
    generation_name="$HOME_CONFIG"
    generation_ref="$home_ref"
    generation_build="$home_ref.activationPackage"
    generation_active=$(home_profile)
    generation_preview=home-preview
    generation_label="Home Manager ($HOME_CONFIG)"
    ;;
  *)
    printf 'Unsupported generation kind: %s\n' "$generation_kind" >&2
    return 1
    ;;
  esac
  generation_desired="$generation_build.outPath"
  generation_saved=$(saved_preview_link "$generation_kind" "$generation_name")
}

# Review only managed files and one known non-secret session preference.
review_home_generation() {
  local actual="$1" profile="$2" files old_files='' path desired active
  files=$(readlink -f "$actual/home-files")
  if [[ -e "$profile/home-files" ]]; then
    old_files=$(readlink -f "$profile/home-files")
  fi
  echo 'Managed home files:'
  find "$files" -type l -printf '  ~/%P\n' | sort
  while IFS= read -r path; do
    if [[ -e "$HOME/$path" || -L "$HOME/$path" ]]; then
      if [[ -z "$old_files" || ! -L "$HOME/$path" || "$(readlink "$HOME/$path")" != "$old_files/$path" ]]; then
        printf 'Already present (review before switching): ~/%s\n' "$path"
      fi
    fi
  done < <(find "$files" -type l -printf '%P\n')
  if [[ -n "$old_files" ]]; then
    while IFS= read -r path; do
      if [[ ! -L "$files/$path" ]]; then
        printf 'No longer managed: ~/%s\n' "$path"
      fi
    done < <(find "$old_files" -type l -printf '%P\n' | sort)
  fi

  desired=$(nix eval --raw --no-write-lock-file \
    --apply 'settings: if builtins.hasAttr "org/gnome/desktop/input-sources" settings && builtins.hasAttr "sources" settings."org/gnome/desktop/input-sources" then builtins.toString settings."org/gnome/desktop/input-sources".sources else ""' \
    "$generation_ref.config.dconf.settings")
  if [[ -z "$desired" ]]; then
    echo 'No GNOME input sources declared by this Home output.'
  else
    active=$(dconf read /org/gnome/desktop/input-sources/sources)
    printf 'GNOME input sources (dconf; GVariant formatting may differ):\n'
    printf '  Active: %s\n  Desired: %s\n' "${active:-(unset)}" "$desired"
  fi
}

preview_generation() (
  local actual candidate rooted
  select_generation "$1"
  candidate=$(create_preview_root "$generation_saved")
  trap 'cleanup_preview_root "$generation_saved" "$candidate"' EXIT
  actual=$(nix build --no-write-lock-file --out-link "$candidate/result" --print-out-paths "$generation_build")
  rooted=$(saved_preview_target "$candidate/result")
  if [[ "$rooted" != "$actual" ]]; then
    echo 'Built generation does not match its candidate GC root; refusing to save preview.' >&2
    return 1
  fi
  if [[ -e "$generation_active" || "$generation_kind" == system ]]; then
    nix store diff-closures "$generation_active" "$actual"
  else
    echo 'No prior Home Manager profile; this would be the first activation'
  fi
  if [[ "$generation_kind" == home ]]; then
    review_home_generation "$actual" "$generation_active"
  fi
  # Publish only the exact built path, after every applicable review succeeds.
  publish_preview_root "$generation_saved" "$candidate"
)

require_system_host() {
  local configured_host current_host
  configured_host=$(nix eval --raw --no-write-lock-file "$generation_ref.config.networking.hostName")
  current_host=$(hostname)
  if [[ -z "$configured_host" ]]; then
    echo 'The selected NixOS configuration has no hostname' >&2
    return 1
  fi
  if [[ "$current_host" != "$configured_host" ]]; then
    if [[ "${ALLOW_HOST_RENAME:-}" != 1 ]]; then
      printf 'Host mismatch: running %s, selected %s (%s). To deliberately rename this host, use ALLOW_HOST_RENAME=1 just switch.\n' \
        "$current_host" "$configured_host" "$generation_name" >&2
      return 1
    fi
    printf 'Opted in to hostname change: %s -> %s\n' "$current_host" "$configured_host"
  fi
}

switch_generation() {
  local actual
  select_generation "$1"
  if [[ "$generation_kind" == system ]]; then
    require_system_host
  fi
  actual=$(require_saved_preview_build "$generation_desired" "$generation_saved" "$generation_preview")
  # Nothing may re-evaluate or rebuild after the saved-build guard.
  if [[ "$generation_kind" == system ]]; then
    sudo nixos-rebuild switch --no-reexec --store-path "$actual"
  else
    if [[ ! -x "$actual/activate" || ! -f "$actual/gen-version" || "$(<"$actual/gen-version")" != 1 ]]; then
      echo 'Saved Home generation does not support driver-version 1; refusing to switch.' >&2
      return 1
    fi
    mkdir -p "$(dirname "$generation_active")"
    nix-env --profile "$generation_active" --set "$actual"
    "$actual/activate" --driver-version 1
  fi
}

show_generation_status() {
  local active desired_available=1
  select_generation "$1"
  active=$(generation_target "$generation_active")
  inspect_saved_preview_build "$generation_desired" "$generation_saved" || desired_available=0

  printf '%s\n' "$generation_label"
  printf '  Active: %s\n' "$active"
  printf '  Saved preview build: %s\n' "$saved_preview_build_target"
  if [[ "$desired_available" == 0 ]]; then
    printf '  Desired: unavailable (flake evaluation failed; check new .nix files with just check)\n'
    evaluation_errors=$((evaluation_errors + 1))
    return
  fi
  printf '  Desired from flake: %s\n' "$saved_preview_build_desired"
  if [[ "$active" == "$saved_preview_build_desired" && "$saved_preview_build_state" == current ]]; then
    echo '  State: active and saved build match the flake.'
  elif [[ "$active" == "$saved_preview_build_desired" ]]; then
    printf '  State: active matches the flake; saved build is missing/stale (run just %s before a future switch).\n' "$generation_preview"
  elif [[ "$saved_preview_build_state" == current ]]; then
    printf '  State: saved build matches the flake, but is NOT active. Review just %s before switching.\n' "$generation_preview"
  else
    printf '  State: neither active nor saved build matches the flake (run just %s).\n' "$generation_preview"
  fi
}

usage() {
  echo 'usage: generation.sh preview|switch system|home OR generation.sh status' >&2
  exit 2
}

case "${1:-}" in
preview | switch)
  [[ $# == 2 ]] || usage
  "${1}_generation" "$2"
  ;;
status)
  [[ $# == 1 ]] || usage
  evaluation_errors=0
  show_generation_status system
  echo
  show_generation_status home
  ((evaluation_errors == 0))
  ;;
*) usage ;;
esac
