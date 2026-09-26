#!/usr/bin/env bash
# Exercise preview/switch commands without building or activating real generations.
# Scenario subshells deliberately isolate exported fixture state.
# shellcheck disable=SC2030,SC2031
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

test_root=$(mktemp -d "${TMPDIR:-/tmp}/system-workflow-tests.XXXXXXXX")
trap 'rm -rf -- "$test_root"' EXIT
mkdir -p "$test_root/bin" "$test_root/generation/home-files"

cat >"$test_root/bin/nix" <<'SH'
#!/usr/bin/env bash
case "$*" in
  build\ --no-write-lock-file*)
    case "$*" in
      *'.#nixosConfigurations.'*) target="$TEST_SYSTEM_EXPECTED" ;;
      *'.#homeConfigurations.'*) target="$TEST_EXPECTED" ;;
      *) printf 'Unexpected build: %s\n' "$*" >&2; exit 1 ;;
    esac
    [[ "$*" == *'--no-link --print-out-paths'* ]] || {
      printf 'Preview build must use --no-link --print-out-paths: %s\n' "$*" >&2
      exit 1
    }
    printf '%s\n' "$*" >> "$TEST_BUILD_LOG"
    printf '%s\n' "$target" ;;
  store\ diff-closures*)
    [[ $(readlink -f "$4") == "$TEST_DIFF_EXPECTED" ]] || {
      printf 'Compared the wrong saved build: %s\n' "$4" >&2
      exit 1
    }
    [[ -z "${TEST_FAIL_DIFF:-}" ]] || exit 1
    ;;
  *--apply*'.#homeConfigurations') printf '%s\n' "$TEST_HOME_NAMES" ;;
  *--apply*'.#nixosConfigurations') printf '%s\n' "$TEST_SYSTEM_NAMES" ;;
  *'.config.home.username') printf '%s\n' "$TEST_USER" ;;
  *'.config.home.homeDirectory') printf '%s\n' "$TEST_HOME" ;;
  *'.activationPackage.outPath') printf '%s\n' "$TEST_EXPECTED" ;;
  *'.config.dconf.settings') printf '%s\n' "$TEST_SOURCES" ;;
  *'.config.networking.hostName') printf '%s\n' "$TEST_HOST" ;;
  *'.config.system.build.toplevel.outPath') printf '%s\n' "$TEST_SYSTEM_EXPECTED" ;;
  *) printf 'Unexpected nix call: %s\n' "$*" >&2; exit 1 ;;
esac
SH
cat >"$test_root/bin/nix-env" <<'SH'
#!/usr/bin/env bash
printf 'profile %s\n' "$*" >> "$TEST_LOG"
SH
cat >"$test_root/bin/hostname" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "${TEST_RUNNING_HOST:-$TEST_HOST}"
SH
cat >"$test_root/bin/sudo" <<'SH'
#!/usr/bin/env bash
printf 'system %s\n' "$*" >> "$TEST_LOG"
SH
cat >"$test_root/generation/activate" <<'SH'
#!/usr/bin/env bash
printf 'activate %s %s\n' "$0" "$*" >> "$TEST_LOG"
SH
chmod +x "$test_root/bin/"* "$test_root/generation/activate"
printf '1\n' >"$test_root/generation/gen-version"

export PATH="$test_root/bin:$PATH"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

# Give every scenario its own environment, saved links, generations, and action logs.
start_case() {
  case_root="$test_root/cases/$1"
  mkdir -p "$case_root/state/nixos" "$case_root/state/nix/profiles" "$case_root/home"
  cp -a "$test_root/generation" "$case_root/generation"
  export HOME="$case_root/home" XDG_STATE_HOME="$case_root/state"
  export TEST_HOME_NAMES='test-user@host-a'
  export TEST_SYSTEM_NAMES=host-a TEST_HOST=host-a
  TEST_USER=$(id -un) || return 1
  export TEST_USER TEST_HOME="$HOME"
  export TEST_EXPECTED="$case_root/generation" TEST_SYSTEM_EXPECTED="$case_root/generation"
  export TEST_LOG="$case_root/actions" TEST_BUILD_LOG="$case_root/builds"
  export TEST_DIFF_EXPECTED="$case_root/generation"
  export TEST_SOURCES=''
  unset NIXOS_CONFIG HOME_CONFIG TEST_RUNNING_HOST TEST_FAIL_DIFF
}

# Selection stays explicit when a flake has several outputs.
(
  start_case selection
  source scripts/config.sh
  select_system || fail 'automatic NixOS selection'
  select_home || fail 'automatic Home selection'
  [[ "$NIXOS_CONFIG" == host-a && "$HOME_CONFIG" == test-user@host-a ]] || fail 'selected wrong sole outputs'

  unset NIXOS_CONFIG HOME_CONFIG
  export TEST_SYSTEM_NAMES=$'host-a\nhost-b'
  export TEST_HOME_NAMES=$'test-user@host-a\ntest-user@host-b'
  if select_system >"$case_root/output" 2>&1; then
    fail 'ambiguous NixOS selection succeeded'
  fi
  if select_home >"$case_root/output" 2>&1; then
    fail 'ambiguous Home selection succeeded'
  fi
  NIXOS_CONFIG=host-b HOME_CONFIG=test-user@host-b
  select_system || fail 'explicit NixOS selection'
  select_home || fail 'explicit Home selection'
)

# Status never builds or activates.
(
  start_case read-only
  just status >"$case_root/output" 2>&1 || fail 'status'
  [[ ! -s "$TEST_BUILD_LOG" && ! -s "$TEST_LOG" ]] || fail 'read-only command built or activated'
)

# A preview publishes a link only after its comparison succeeds.
(
  start_case preview
  system_link="$XDG_STATE_HOME/nixos/result-system-host-a"
  just preview >"$case_root/output" 2>&1 || fail 'system preview'
  [[ $(readlink -f "$system_link") == "$case_root/generation" ]] || fail 'system preview saved wrong build'
  [[ ! -s "$TEST_LOG" ]] || fail 'system preview activated'

  rm "$system_link"
  if TEST_FAIL_DIFF=1 just preview >"$case_root/output" 2>&1; then
    fail 'failed system comparison succeeded'
  fi
  [[ ! -e "$system_link" ]] || fail 'failed system comparison saved a build'
  if just switch >"$case_root/output" 2>&1; then
    fail 'system switch accepted a failed preview'
  fi

  home_link="$XDG_STATE_HOME/nixos/result-home-test-user@host-a"
  ln -s "$case_root/generation" "$XDG_STATE_HOME/nix/profiles/home-manager"
  if TEST_FAIL_DIFF=1 just home-preview >"$case_root/output" 2>&1; then
    fail 'failed Home comparison succeeded'
  fi
  [[ ! -e "$home_link" ]] || fail 'failed Home comparison saved a build'
  if just home-switch >"$case_root/output" 2>&1; then
    fail 'Home switch accepted a failed preview'
  fi
  just home-preview >"$case_root/output" 2>&1 || fail 'Home preview'
  [[ $(readlink -f "$home_link") == "$case_root/generation" ]] || fail 'Home preview saved wrong build'
  [[ ! -s "$TEST_LOG" ]] || fail 'Home preview activated'
)

# System switch uses a current preview and checks the running hostname.
(
  start_case system-switch
  ln -s "$case_root/generation" "$XDG_STATE_HOME/nixos/result-system"
  if just switch >"$case_root/output" 2>&1; then
    fail 'legacy shared system build was activated'
  fi
  just preview >"$case_root/output" 2>&1 || fail 'system preview before switch'

  export TEST_SYSTEM_EXPECTED="$case_root/other-generation"
  if just switch >"$case_root/output" 2>&1; then
    fail 'stale system preview was activated'
  fi
  export TEST_SYSTEM_EXPECTED="$case_root/generation" TEST_RUNNING_HOST=host-b
  if just switch >"$case_root/output" 2>&1; then
    fail 'wrong running host was switched'
  fi
  [[ ! -s "$TEST_LOG" ]] || fail 'rejected system switch activated'
  grep -Fq 'Host mismatch' "$case_root/output" || fail 'hostname mismatch was not explained'

  export TEST_RUNNING_HOST=host-a
  just switch >"$case_root/output" 2>&1 || fail 'current system preview was not switched'
  grep -Fxq "system nixos-rebuild switch --no-reexec --store-path $case_root/generation" "$TEST_LOG" || fail 'system switch used wrong build'
)

# Home identity and saved-build checks run before activation.
(
  start_case home-switch
  export TEST_USER=another-user
  if just home-preview >"$case_root/output" 2>&1; then
    fail 'foreign Home output was previewed'
  fi
  [[ ! -s "$TEST_BUILD_LOG" ]] || fail 'foreign Home output was built'
  TEST_USER=$(id -un)
  export TEST_USER TEST_HOME="$case_root/other-home"
  if just home-preview >"$case_root/output" 2>&1; then
    fail 'foreign home directory was previewed'
  fi
  export TEST_HOME="$HOME"
  just home-preview >"$case_root/output" 2>&1 || fail 'owned Home preview'

  export TEST_USER=another-user
  if just home-switch >"$case_root/output" 2>&1; then
    fail 'foreign Home output was activated'
  fi
  if just status >"$case_root/output" 2>&1; then
    fail 'status reported the caller as a foreign Home output'
  fi
  TEST_USER=$(id -un)
  export TEST_USER
  export TEST_EXPECTED="$case_root/other-generation"
  if just home-switch >"$case_root/output" 2>&1; then
    fail 'stale Home preview was activated'
  fi
  export TEST_EXPECTED="$case_root/generation"
  home_link="$XDG_STATE_HOME/nixos/result-home-test-user@host-a"
  rm "$home_link"
  mkdir "$home_link"
  if just home-switch >"$case_root/output" 2>&1; then
    fail 'plain directory was used as a preview'
  fi
  rmdir "$home_link"
  ln -s "$case_root/generation" "$home_link"

  printf '2\n' >"$case_root/generation/gen-version"
  if just home-switch >"$case_root/output" 2>&1; then
    fail 'unsupported Home driver was activated'
  fi
  [[ ! -s "$TEST_LOG" ]] || fail 'rejected Home switch changed the profile'
  printf '1\n' >"$case_root/generation/gen-version"

  just home-switch >"$case_root/output" 2>&1 || fail 'current Home preview was not switched'
  grep -Fxq "profile --profile $XDG_STATE_HOME/nix/profiles/home-manager --set $case_root/generation" "$TEST_LOG" || fail 'Home profile used wrong build'
  grep -Fxq "activate $case_root/generation/activate --driver-version 1" "$TEST_LOG" || fail 'Home activation used wrong build'
  [[ $(wc -l <"$TEST_LOG") -eq 2 ]] || fail 'Home switch performed extra actions'
)

printf 'Workflow tests passed.\n'
