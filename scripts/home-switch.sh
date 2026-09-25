#!/usr/bin/env bash
# Activate only the saved Home Manager generation after checking its owner and freshness.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/config.sh
source scripts/saved-preview-build.sh

select_home
configured_user=$(nix eval --raw --no-write-lock-file "$home_ref.config.home.username")
configured_home=$(nix eval --raw --no-write-lock-file "$home_ref.config.home.homeDirectory")
if [[ "$configured_user" != "$(id -un)" || "$configured_home" != "$HOME" ]]; then
  printf 'Home output %s belongs to %s (%s), not %s (%s). Refusing to switch.\n' \
    "$HOME_CONFIG" "$configured_user" "$configured_home" "$(id -un)" "$HOME" >&2
  exit 1
fi

result="${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-home"
actual=$(require_saved_preview_build "$home_ref.activationPackage.outPath" "$result" home-preview)
if [[ ! -x "$actual/activate" || ! -f "$actual/gen-version" || "$(cat "$actual/gen-version")" != 1 ]]; then
  echo 'Saved Home generation does not support driver-version 1; refusing to switch.' >&2
  exit 1
fi

# Match the pinned Home Manager switch driver: set the generation profile first,
# then activate that exact generation. Never re-evaluate or rebuild after the guard.
profile=$(home_profile)
mkdir -p "$(dirname "$profile")"
nix-env --profile "$profile" --set "$actual"
"$actual/activate" --driver-version 1
