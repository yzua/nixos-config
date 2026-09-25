#!/usr/bin/env bash
# Resolve saved preview builds and the active Home Manager profile consistently.

generation_target() {
  if [[ -e "$1" ]]; then
    readlink -f "$1"
  elif [[ -L "$1" ]]; then
    printf 'broken symlink (%s)\n' "$1"
  else
    printf 'missing (%s)\n' "$1"
  fi
}

desired_generation() {
  nix eval --raw --no-write-lock-file "$1"
}

require_saved_preview_build() {
  local output="$1" result="$2" preview="$3" expected actual
  if [[ ! -L "$result" || ! -e "$result" ]]; then
    printf 'No valid saved preview build; run just %s first\n' "$preview" >&2
    return 1
  fi

  expected=$(desired_generation "$output") || return 1
  actual=$(readlink -f "$result") || return 1
  if [[ "$actual" != "$expected" ]]; then
    printf 'Saved preview build is stale; run just %s first\n' "$preview" >&2
    return 1
  fi
  printf '%s\n' "$actual"
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
