#!/usr/bin/env bash
# Source this from just recipes or scripts to select flake outputs.
# Set NIXOS_CONFIG / HOME_CONFIG when a flake has multiple outputs.

flake_output_names() {
  nix eval --raw --no-write-lock-file \
    --apply 'outputs: builtins.concatStringsSep "\n" (builtins.attrNames outputs)' \
    ".#$1"
}

has_output() {
  grep -Fxq -- "$1" <<<"$2"
}

valid_output_name() {
  [[ "$1" =~ ^[a-zA-Z0-9_.@-]+$ ]]
}

select_output() {
  local group="$1" variable="$2" candidate="$3" names
  names=$(flake_output_names "$group") || return 1
  if [[ -z "$names" ]]; then
    printf 'No %s outputs in this flake.\n' "$group" >&2
    return 1
  fi
  if [[ -z "$candidate" ]]; then
    if [[ "$names" == *$'\n'* ]]; then
      printf 'Multiple %s outputs. Set %s to one of:\n%s\n' "$group" "$variable" "$names" >&2
      return 1
    fi
    candidate="$names"
  fi
  if ! valid_output_name "$candidate" || ! has_output "$candidate" "$names"; then
    printf 'Invalid %s=%s; available outputs:\n%s\n' "$variable" "$candidate" "$names" >&2
    return 1
  fi
  printf '%s\n' "$candidate"
}

select_system() {
  NIXOS_CONFIG=$(select_output nixosConfigurations NIXOS_CONFIG "${NIXOS_CONFIG:-}") || return 1
  # Consumed by scripts and just recipes that source this file.
  # shellcheck disable=SC2034
  system_ref=".#nixosConfigurations.\"${NIXOS_CONFIG}\""
  export NIXOS_CONFIG
}

select_home() {
  HOME_CONFIG=$(select_output homeConfigurations HOME_CONFIG "${HOME_CONFIG:-}") || return 1
  # Consumed by scripts and just recipes that source this file.
  # shellcheck disable=SC2034
  home_ref=".#homeConfigurations.\"${HOME_CONFIG}\""
  export HOME_CONFIG
}

require_home_owner() {
  local configured_user configured_home
  configured_user=$(nix eval --raw --no-write-lock-file "$home_ref.config.home.username") || return 1
  configured_home=$(nix eval --raw --no-write-lock-file "$home_ref.config.home.homeDirectory") || return 1
  if [[ "$configured_user" != "$(id -un)" || "$configured_home" != "$HOME" ]]; then
    printf "Home output %s belongs to %s (%s), not %s (%s); refusing to use the caller's Home Manager state.\n" \
      "$HOME_CONFIG" "$configured_user" "$configured_home" "$(id -un)" "$HOME" >&2
    return 1
  fi
}
