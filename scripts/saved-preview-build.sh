#!/usr/bin/env bash
# Own saved-preview build lifecycles, freshness, and the active Home profile.

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

# Begin one terminal preview action in the launched command shell (not a
# command substitution or publication subshell). Own its EXIT trap and expose
# only saved_preview_build_root for the caller's build and review. Publication
# happens separately, so neither building nor reviewing holds the lock.
begin_saved_preview_build() {
  local saved="$1" candidate cleanup_command
  candidate=$(create_preview_root "$saved")
  _saved_preview_build_link="$saved"
  saved_preview_build_root="$candidate/result"
  # Capture escaped values: errexit can unwind function locals before EXIT.
  # Initially no publication descriptor is open yet.
  printf -v cleanup_command 'cleanup_preview_root %q %q' "$saved" "$candidate"
  # shellcheck disable=SC2064 # Arguments must survive function-local unwinding.
  trap "$cleanup_command" EXIT
  # Children inherit this descriptor. Cleanup can then wait for a surviving
  # publisher child before deciding whether it committed the candidate.
  exec {_saved_preview_build_lock}>"$saved.roots/publication.lock"
  printf -v cleanup_command 'cleanup_preview_root %q %q %q' "$saved" "$candidate" "$_saved_preview_build_lock"
  # shellcheck disable=SC2064 # Capture the descriptor as well as the paths.
  trap "$cleanup_command" EXIT
}

# Keep each registered out-link at its original pathname for its whole lifetime.
# The public saved link points through that root, not directly at the store path.
create_preview_root() {
  local saved="$1" directory candidate
  directory="$saved.roots"
  mkdir -p "$directory" || return 1
  directory=$(cd "$directory" && pwd -P) || return 1
  candidate=$(mktemp -d "$directory/candidate.XXXXXXXX") || return 1
  if ! printf '%s\n' "$saved" >"$candidate/owner"; then
    rmdir -- "$candidate"
    return 1
  fi
  printf '%s\n' "$candidate"
}

# Delete only a root allocated by this workflow for this exact saved output.
# Never follow a legacy saved link to remove its target or recursively delete.
discard_preview_root() {
  local saved="$1" root="$2" directory candidate leaf
  [[ "$root" == */result ]] || return 0
  directory=$(cd "$saved.roots" && pwd -P) || return 0
  candidate="${root%/result}"
  [[ "${candidate%/*}" == "$directory" && ! -L "$candidate" ]] || return 0
  leaf="${candidate##*/}"
  [[ "$leaf" =~ ^candidate\.[[:alnum:]]{8}$ ]] || return 0
  [[ -f "$candidate/owner" && ! -L "$candidate/owner" && "$(<"$candidate/owner")" == "$saved" ]] || return 0
  [[ ! -e "$root" || -L "$root" ]] || return 0
  if [[ -L "$candidate/saved" ]]; then
    rm -- "$candidate/saved" || return 1
  fi
  if [[ -L "$root" ]]; then
    rm -- "$root" || return 1
  fi
  rm -- "$candidate/owner" || return 1
  # Leave any unexpected contents alone.
  rmdir -- "$candidate" 2>/dev/null || true
}

cleanup_preview_root() {
  local saved="$1" candidate="$2" lock="${3:-}" cleanup_lock
  # Drop this shell's publication descriptor, then lock a distinct file
  # description. A surviving foreground child (e.g. mv) retains the original
  # lock until it exits, so cleanup cannot race its eventual atomic rename.
  if [[ -n "$lock" ]]; then
    exec {lock}>&-
  fi
  exec {cleanup_lock}>"$saved.roots/publication.lock"
  flock "$cleanup_lock"
  # Also covers a signal immediately after atomic publication: never unroot
  # the candidate now referenced by the public saved link.
  if [[ ! -L "$saved" || "$(readlink "$saved")" != "$candidate/result" ]]; then
    discard_preview_root "$saved" "$candidate/result"
  fi
  exec {cleanup_lock}>&-
}

# Commit the candidate only after the caller's build and review have succeeded.
# EXIT cleanup keeps committed roots and discards uncommitted ones.
publish_saved_preview_build() {
  local saved="$_saved_preview_build_link" candidate="${saved_preview_build_root%/result}"
  local lock="$_saved_preview_build_lock" previous=''
  # Run in the preview shell: no surviving publication subshell may replace
  # the saved alias after signal cleanup has removed its candidate.
  flock "$lock"
  if [[ -L "$saved" ]]; then
    previous=$(readlink "$saved")
  fi
  ln -s "$candidate/result" "$candidate/saved"
  # Only the public alias is renamed; Nix registered candidate/result, not saved.
  mv -Tf -- "$candidate/saved" "$saved"
  if [[ -n "$previous" ]]; then
    discard_preview_root "$saved" "$previous" ||
      printf 'Warning: could not retire superseded preview root: %s\n' "$previous" >&2
  fi
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
