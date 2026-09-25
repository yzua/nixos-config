#!/usr/bin/env bash
# Review a saved Home build's closure, managed files, and declared GNOME sources.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/config.sh
source scripts/saved-preview-build.sh
select_home

result="${XDG_STATE_HOME:-$HOME/.local/state}/nixos/result-home"
require_saved_preview_build "$home_ref.activationPackage.outPath" "$result" home-preview >/dev/null
profile=$(home_profile)
if [[ -e "$profile" ]]; then
  nix store diff-closures "$profile" "$result"
else
  echo 'No prior Home Manager profile; this would be the first activation'
fi

files=$(readlink -f "$result/home-files")
old_files=''
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

# Evaluate one known non-secret preference, not the entire dconf tree. Other
# Home outputs without this setting should still be previewable.
desired=$(nix eval --raw --no-write-lock-file \
  --apply 'settings: if builtins.hasAttr "org/gnome/desktop/input-sources" settings && builtins.hasAttr "sources" settings."org/gnome/desktop/input-sources" then builtins.toString settings."org/gnome/desktop/input-sources".sources else ""' \
  "$home_ref.config.dconf.settings")
if [[ -z "$desired" ]]; then
  echo 'No GNOME input sources declared by this Home output.'
  exit 0
fi

active=$(dconf read /org/gnome/desktop/input-sources/sources)
printf 'GNOME input sources (dconf; GVariant formatting may differ):\n'
printf '  Active: %s\n  Desired: %s\n' "${active:-(unset)}" "$desired"
