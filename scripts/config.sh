#!/usr/bin/env bash
# Source this from just recipes or scripts to select flake outputs. Override
# NIXOS_CONFIG / HOME_CONFIG when a flake has multiple possible outputs.

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

select_system() {
  local names candidate
  names=$(flake_output_names nixosConfigurations) || return 1
  if [[ -z "$names" ]]; then
    echo 'No NixOS outputs in this flake.' >&2
    return 1
  fi

  candidate="${NIXOS_CONFIG:-}"
  if [[ -z "$candidate" ]]; then
    if has_output "$(hostname)" "$names"; then
      candidate=$(hostname)
    elif [[ "$names" != *$'\n'* ]]; then
      candidate="$names"
    else
      printf 'Cannot select a NixOS output for host %s. Set NIXOS_CONFIG to one of:\n%s\n' "$(hostname)" "$names" >&2
      return 1
    fi
  fi

  if ! has_output "$candidate" "$names" || ! valid_output_name "$candidate"; then
    printf 'Invalid NIXOS_CONFIG=%s; available outputs:\n%s\n' "$candidate" "$names" >&2
    return 1
  fi
  NIXOS_CONFIG="$candidate"
  system_ref=".#nixosConfigurations.\"${NIXOS_CONFIG}\""
  export NIXOS_CONFIG
}

select_home() {
  local names candidate conventional configured_user host
  names=$(flake_output_names homeConfigurations) || return 1
  if [[ -z "$names" ]]; then
    echo 'No Home Manager outputs in this flake.' >&2
    return 1
  fi

  candidate="${HOME_CONFIG:-}"
  if [[ -z "$candidate" ]]; then
    # Home-only recipes must not require a NixOS output. An explicit system
    # selection still supplies the host when the caller needs both outputs.
    host=$(hostname)
    if [[ -n "${NIXOS_CONFIG:-}" ]]; then
      if [[ -z "${system_ref:-}" ]]; then
        select_system || return 1
      fi
      host="$NIXOS_CONFIG"
    fi
    conventional="$(id -un)@${host}"
    if has_output "$conventional" "$names"; then
      candidate="$conventional"
    elif [[ "$names" != *$'\n'* ]]; then
      candidate="$names"
      if ! valid_output_name "$candidate"; then
        printf 'Unsupported Home Manager output name: %s\n' "$candidate" >&2
        return 1
      fi
      configured_user=$(nix eval --raw --no-write-lock-file \
        ".#homeConfigurations.\"${candidate}\".config.home.username") || return 1
      if [[ "$configured_user" != "$(id -un)" ]]; then
        printf 'The only Home Manager output (%s) belongs to %s, not %s. Update the home configuration or set HOME_CONFIG explicitly.\n' \
          "$candidate" "$configured_user" "$(id -un)" >&2
        return 1
      fi
    else
      printf 'Cannot select a Home Manager output for %s. Set HOME_CONFIG to one of:\n%s\n' "$conventional" "$names" >&2
      return 1
    fi
  fi

  if ! has_output "$candidate" "$names" || ! valid_output_name "$candidate"; then
    printf 'Invalid HOME_CONFIG=%s; available outputs:\n%s\n' "$candidate" "$names" >&2
    return 1
  fi
  HOME_CONFIG="$candidate"
  # Consumed by scripts and just recipes that source this file.
  # shellcheck disable=SC2034
  home_ref=".#homeConfigurations.\"${HOME_CONFIG}\""
  export HOME_CONFIG
}
