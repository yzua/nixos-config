#!/usr/bin/env bash
# Require a purpose comment at the start of every repo Nix file, including new ones.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

missing=0
checked=0
while IFS= read -r -d '' file; do
  # Tracked paths may be deleted in the working tree; only check files on disk.
  [[ -f "$file" ]] || continue
  ((checked += 1))
  first_line=''
  IFS= read -r first_line <"$file" || true
  if [[ ! "$first_line" =~ ^#[[:blank:]]+[^[:space:]] ]]; then
    printf 'Missing Nix header: %s (start with # <purpose>)\n' "$file" >&2
    ((missing += 1))
  fi
done < <(git ls-files -z --cached --others --exclude-standard -- '*.nix')

if ((missing > 0)); then
  printf '%d of %d Nix files lack a purpose header.\n' "$missing" "$checked" >&2
  exit 1
fi
printf 'All %d Nix files have first-line headers.\n' "$checked"
