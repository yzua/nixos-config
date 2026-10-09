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
# Each foreground fixture preview owns its shell's EXIT trap, just like a
# workflow command, without replacing the parent test's disposable-store trap.
preview_fixture() (
  begin_saved_preview_build "$1"
  # Building an existing store path registers the root without a derivation,
  # download, or dependence on any workstation generation.
  isolated_nix build --offline --no-write-lock-file --out-link "$saved_preview_build_root" "$path"
  publish_saved_preview_build
)
for saved in "$saved_a" "$saved_b"; do
  preview_fixture "$saved"
  root=$(readlink "$saved")
  [[ -L "$root" && $(readlink "$root") == "$path" ]]
  [[ -n $(find "$proof/store/nix/var/nix/gcroots/auto" -type l -lname "$root" -print -quit) ]]
done
a=$(readlink "$saved_a")
b=$(readlink "$saved_b")
find "$proof/store/nix/var/nix/gcroots/auto" -type l -printf 'Registered root: %p -> %l\n'
isolated_nix store gc
[[ -e "$proof/store$path" && -L "$a" && -L "$b" ]]
echo 'PASS: published roots retain the unactivated shared target through GC.'

preview_fixture "$saved_a"
next_a=$(readlink "$saved_a")
[[ ! -L "$a" && -L "$next_a" && -L "$b" ]]
echo "PASS: successful publication retires only the same output's previous root."

rm -- "$next_a"
isolated_nix store gc
[[ -e "$proof/store$path" ]]
echo 'PASS: the other output independently retains the shared target.'
rm -- "$b"
isolated_nix store gc
[[ ! -e "$proof/store$path" ]]
echo 'PASS: removing the final root makes the isolated fixture collectible.'
echo 'Isolated saved-preview GC proof passed; no workstation GC performed.'
