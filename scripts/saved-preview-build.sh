#!/usr/bin/env bash
# Resolve per-output saved preview builds and the active Home Manager profile.

saved_preview_link() {
  local kind="$1" output="$2"
  case "$kind" in
  system | home) printf '%s/nixos/result-%s-%s\n' "${XDG_STATE_HOME:-$HOME/.local/state}" "$kind" "$output" ;;
  *)
    printf 'Unsupported preview kind: %s\n' "$kind" >&2
    return 1
    ;;
  esac
}

generation_target() {
  if [[ -e "$1" ]]; then
    readlink -f "$1"
  elif [[ -L "$1" ]]; then
    printf 'broken symlink (%s)\n' "$1"
  else
    printf 'missing (%s)\n' "$1"
  fi
}

saved_preview_target() {
  if [[ -L "$1" ]]; then
    if [[ -e "$1" ]]; then
      readlink -f "$1"
    else
      printf 'broken symlink (%s)\n' "$1"
      return 1
    fi
  elif [[ -e "$1" ]]; then
    printf 'not a symlink (%s)\n' "$1"
    return 1
  else
    printf 'missing (%s)\n' "$1"
    return 1
  fi
}

desired_generation() {
  nix eval --raw --no-write-lock-file "$1"
}

# Status and activation share one verdict for the selected output's saved build.
# Leave the diagnostic target available even when the link is invalid.
inspect_saved_preview_build() {
  local output="$1" result="$2"
  if saved_preview_build_target=$(saved_preview_target "$result"); then
    saved_preview_build_state=stale
  else
    saved_preview_build_state=invalid
  fi
  saved_preview_build_desired=$(desired_generation "$output") || return 1
  if [[ "$saved_preview_build_state" == stale && "$saved_preview_build_target" == "$saved_preview_build_desired" ]]; then
    saved_preview_build_state=current
  fi
}

require_saved_preview_build() {
  local output="$1" result="$2" preview="$3"
  if ! inspect_saved_preview_build "$output" "$result"; then
    [[ "$saved_preview_build_state" == invalid ]] || return 1
  fi
  case "$saved_preview_build_state" in
  invalid)
    printf 'No valid saved preview build; run just %s first\n' "$preview" >&2
    return 1
    ;;
  stale)
    printf 'Saved preview build is stale; run just %s first\n' "$preview" >&2
    return 1
    ;;
  current) printf '%s\n' "$saved_preview_build_target" ;;
  *)
    printf 'Cannot determine saved preview build state\n' >&2
    return 1
    ;;
  esac
}

home_profile() {
  local state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
  local user_profiles="$state_home/nix/profiles"
  local global_profiles
  global_profiles="${NIX_STATE_DIR:-/nix/var/nix}/profiles/per-user/$(id -un)"
  if [[ -d "$user_profiles" || ! -d "$global_profiles" ]]; then
    printf '%s/home-manager\n' "$user_profiles"
  else
    printf '%s/home-manager\n' "$global_profiles"
  fi
}
