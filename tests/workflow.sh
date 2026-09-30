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
if [[ "${TEST_FAIL_DESIRED:-}" == 1 && "$*" == *'.outPath'* ]]; then
  echo 'Fixture flake evaluation failed' >&2
  exit 1
fi
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
cat >"$test_root/bin/dconf" <<'SH'
#!/usr/bin/env bash
[[ "$*" == 'read /org/gnome/desktop/input-sources/sources' ]] || exit 1
[[ "${TEST_FAIL_DCONF:-}" != 1 ]] || exit 1
printf '%s\n' "$TEST_ACTIVE_SOURCES"
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
  export TEST_SOURCES='' TEST_ACTIVE_SOURCES=''
  unset NIXOS_CONFIG HOME_CONFIG TEST_RUNNING_HOST TEST_FAIL_DIFF TEST_FAIL_DESIRED TEST_FAIL_DCONF
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
  for command in preview home-preview switch home-switch status; do
    if just "$command" >"$case_root/output" 2>&1; then
      fail 'ambiguous generation command succeeded'
    fi
  done
  [[ ! -s "$TEST_BUILD_LOG" && ! -s "$TEST_LOG" ]] || fail 'ambiguous selection built or activated'
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

# Home review preserves file conflict reporting and narrowly scoped dconf review.
(
  start_case home-review
  mkdir -p "$case_root/old-generation/home-files/.config" "$case_root/generation/home-files/.config" "$HOME/.config"
  printf 'managed content\n' >"$case_root/content"
  for name in still removed; do
    ln -s "$case_root/content" "$case_root/old-generation/home-files/.config/$name"
  done
  for name in still conflict; do
    ln -s "$case_root/content" "$case_root/generation/home-files/.config/$name"
  done
  ln -s "$case_root/old-generation/home-files/.config/still" "$HOME/.config/still"
  printf 'existing user file\n' >"$HOME/.config/conflict"
  ln -s "$case_root/old-generation" "$XDG_STATE_HOME/nix/profiles/home-manager"
  export TEST_SOURCES="[('xkb', 'us'), ('xkb', 'ara')]" TEST_ACTIVE_SOURCES="[('xkb', 'us')]"
  just home-preview >"$case_root/output" 2>&1 || fail 'Home managed-file review'
  grep -Fq 'Already present (review before switching): ~/.config/conflict' "$case_root/output" || fail 'missing file conflict'
  if grep -Fq 'Already present (review before switching): ~/.config/still' "$case_root/output"; then
    fail 'previously managed file reported as conflict'
  fi
  grep -Fq 'No longer managed: ~/.config/removed' "$case_root/output" || fail 'missing removed file report'
  grep -Fq "Active: $TEST_ACTIVE_SOURCES" "$case_root/output" || fail 'missing active input sources'
  grep -Fq "Desired: $TEST_SOURCES" "$case_root/output" || fail 'missing desired input sources'
  [[ ! -s "$TEST_LOG" ]] || fail 'Home review activated'
  rm "$XDG_STATE_HOME/nixos/result-home-test-user@host-a"
  if TEST_FAIL_DCONF=1 just home-preview >"$case_root/output" 2>&1; then
    fail 'failed session preference review succeeded'
  fi
  [[ ! -e "$XDG_STATE_HOME/nixos/result-home-test-user@host-a" ]] || fail 'failed Home review published a build'
)

# Different outputs retain independent previews even when their paths coincide.
(
  start_case output-retention
  export TEST_SYSTEM_NAMES=$'host-a\nhost-b'
  export TEST_HOME_NAMES=$'test-user@host-a\ntest-user@host-b'
  NIXOS_CONFIG=host-a just preview >"$case_root/output" 2>&1 || fail 'first system output preview'
  NIXOS_CONFIG=host-b just preview >"$case_root/output" 2>&1 || fail 'second system output preview'
  HOME_CONFIG=test-user@host-a just home-preview >"$case_root/output" 2>&1 || fail 'first Home output preview'
  HOME_CONFIG=test-user@host-b just home-preview >"$case_root/output" 2>&1 || fail 'second Home output preview'
  for kind in system home; do
    for name in host-a host-b; do
      output="$name"
      [[ "$kind" != home ]] || output="test-user@$name"
      [[ $(readlink -f "$XDG_STATE_HOME/nixos/result-$kind-$output") == "$case_root/generation" ]] || fail 'per-output shared-path retention'
    done
  done
)

# A failed later preview must not replace the previous successfully saved build.
(
  start_case failed-repreview
  just preview >"$case_root/output" 2>&1 || fail 'initial system preview'
  just home-preview >"$case_root/output" 2>&1 || fail 'initial Home preview'
  ln -s "$case_root/generation" "$XDG_STATE_HOME/nix/profiles/home-manager"
  cp -a "$case_root/generation" "$case_root/new-generation"
  export TEST_EXPECTED="$case_root/new-generation" TEST_SYSTEM_EXPECTED="$case_root/new-generation"
  export TEST_DIFF_EXPECTED="$case_root/new-generation" TEST_FAIL_DIFF=1
  for command in preview home-preview; do
    if just "$command" >"$case_root/output" 2>&1; then
      fail 'failed later comparison succeeded'
    fi
  done
  [[ $(readlink -f "$XDG_STATE_HOME/nixos/result-system-host-a") == "$case_root/generation" ]] || fail 'failed re-preview replaced system build'
  [[ $(readlink -f "$XDG_STATE_HOME/nixos/result-home-test-user@host-a") == "$case_root/generation" ]] || fail 'failed re-preview replaced Home build'
  for command in switch home-switch; do
    if just "$command" >"$case_root/output" 2>&1; then
      fail 'previous preview activated despite changed desired generation'
    fi
  done
  [[ ! -s "$TEST_LOG" ]] || fail 'failed re-preview activated'
)

# Failed desired-generation evaluation must never authorize a saved build.
(
  start_case evaluation-failure
  just preview >"$case_root/output" 2>&1 || fail 'system preview before evaluation failure'
  just home-preview >"$case_root/output" 2>&1 || fail 'Home preview before evaluation failure'
  export TEST_FAIL_DESIRED=1
  for command in status switch home-switch; do
    if just "$command" >"$case_root/output" 2>&1; then
      fail 'failed desired evaluation reported success'
    fi
  done
  [[ ! -s "$TEST_LOG" ]] || fail 'failed evaluation activated'
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

  TEST_RUNNING_HOST=host-b ALLOW_HOST_RENAME=1 just switch >"$case_root/output" 2>&1 || fail 'explicit hostname rename was refused'
  grep -Fq 'Opted in to hostname change: host-b -> host-a' "$case_root/output" || fail 'explicit hostname rename was not explained'
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
