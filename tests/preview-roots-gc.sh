#!/usr/bin/env bash
# Prove saved-preview retention using only a disposable, isolated local Nix store.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source scripts/saved-preview-build.sh

proof=$(mktemp -d "${TMPDIR:-/tmp}/preview-roots-gc.XXXXXXXX")
trap 'chmod -R u+w -- "$proof"; rm -rf -- "$proof"' EXIT
# The local-store URI must refer only to the freshly allocated directory; reject
# URI delimiters/escapes in a caller-provided TMPDIR rather than risking ambiguity.
[[ "$proof" == /* && "$proof" != *'?'* && "$proof" != *'&'* && "$proof" != *'#'* && "$proof" != *'%'* ]]
unset NIX_STORE_DIR NIX_STATE_DIR
store="local?root=$proof/store"
isolated_nix() {
  nix --extra-experimental-features nix-command --store "$store" "$@"
}
printf 'Isolated store: %s\n' "$store"
mkdir "$proof/fixture"
printf 'Isolated per-output GC fixture: %s\n' "$proof" >"$proof/fixture/content"
path=$(isolated_nix store add-path "$proof/fixture")
[[ "$path" == /nix/store/* && -e "$proof/store$path" ]]
printf 'Logical fixture: %s\n' "$path"

saved_a="$proof/state/result-system-output-a"
saved_b="$proof/state/result-system-output-b"
a=$(create_preview_root "$saved_a")
b=$(create_preview_root "$saved_b")
for output in a b; do
  saved_var="saved_$output"
  saved="${!saved_var}"
  candidate="${!output}"
  exec {publication_lock}>"$saved.roots/publication.lock"
  # Building an existing store path registers the root without a derivation,
  # download, or dependence on any workstation generation.
  isolated_nix build --offline --no-write-lock-file --out-link "$candidate/result" "$path"
  publish_preview_root "$saved" "$candidate" "$publication_lock"
  cleanup_preview_root "$saved" "$candidate" "$publication_lock"
  [[ $(readlink "$saved") == "$candidate/result" ]]
  [[ -n $(find "$proof/store/nix/var/nix/gcroots/auto" -type l -lname "$candidate/result" -print -quit) ]]
done
find "$proof/store/nix/var/nix/gcroots/auto" -type l -printf 'Registered root: %p -> %l\n'
isolated_nix store gc
[[ -e "$proof/store$path" && -L "$a/result" && -L "$b/result" ]]
echo 'PASS: published roots retain the unactivated shared target through GC.'

next_a=$(create_preview_root "$saved_a")
exec {publication_lock}>"$saved_a.roots/publication.lock"
isolated_nix build --offline --no-write-lock-file --out-link "$next_a/result" "$path"
publish_preview_root "$saved_a" "$next_a" "$publication_lock"
cleanup_preview_root "$saved_a" "$next_a" "$publication_lock"
[[ ! -L "$a/result" && -L "$next_a/result" && -L "$b/result" ]]
echo "PASS: successful publication retires only the same output's previous root."

discard_preview_root "$saved_a" "$next_a/result"
isolated_nix store gc
[[ -e "$proof/store$path" ]]
echo 'PASS: the other output independently retains the shared target.'
discard_preview_root "$saved_b" "$b/result"
isolated_nix store gc
[[ ! -e "$proof/store$path" ]]
echo 'PASS: removing the final root makes the isolated fixture collectible.'
echo 'Isolated saved-preview GC proof passed; no workstation GC performed.'
