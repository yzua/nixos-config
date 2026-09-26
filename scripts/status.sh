#!/usr/bin/env bash
# Compare flake outputs with saved preview builds and active generations.
# This script evaluates only: it never builds or activates either configuration.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/config.sh
source scripts/saved-preview-build.sh

evaluation_errors=0

show_status() {
  local label="$1" output="$2" active_link="$3" built_link="$4" preview="$5"
  local active desired_available=1
  active=$(generation_target "$active_link")
  inspect_saved_preview_build "$output" "$built_link" || desired_available=0

  printf '%s\n' "$label"
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
    printf '  State: active matches the flake; saved build is missing/stale (run just %s before a future switch).\n' "$preview"
  elif [[ "$saved_preview_build_state" == current ]]; then
    printf '  State: saved build matches the flake, but is NOT active. Review just %s before switching.\n' "$preview"
  else
    printf '  State: neither active nor saved build matches the flake (run just %s).\n' "$preview"
  fi
}

select_system
show_status "NixOS ($NIXOS_CONFIG)" \
  "$system_ref.config.system.build.toplevel.outPath" \
  /run/current-system "$(saved_preview_link system "$NIXOS_CONFIG")" preview
echo
select_home
require_home_owner
show_status "Home Manager ($HOME_CONFIG)" \
  "$home_ref.activationPackage.outPath" \
  "$(home_profile)" "$(saved_preview_link home "$HOME_CONFIG")" home-preview

if ((evaluation_errors > 0)); then
  exit 1
fi
