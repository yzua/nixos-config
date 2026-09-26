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
    while (($#)); do
      if [[ "$1" == --out-link ]]; then
        ln -sfn "$target" "$2"
        exit
      fi
      shift
    done
    printf 'Missing build out-link\n' >&2
    exit 1 ;;
  store\ diff-closures*)
    if [[ -n "${TEST_RETARGET_ON_DIFF:-}" ]]; then
      ln -sfn "$TEST_RETARGET_ON_DIFF" "$TEST_RETARGET_LINK"
    fi
    [[ $(readlink -f "$4") == "$TEST_DIFF_EXPECTED" ]] || {
      printf 'Compared the wrong saved build: %s\n' "$4" >&2
      exit 1
    }
    printf 'diff %s\n' "$4" >> "$TEST_DIFF_LOG" ;;
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
test "$*" = 'read /org/gnome/desktop/input-sources/sources'
printf '%s\n' "$TEST_ACTIVE_SOURCES"
SH
cat >"$test_root/bin/hostname" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$TEST_HOST"
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
  mkdir -p "$case_root/state/nixos" "$case_root/state/nix/profiles"
  cp -a "$test_root/generation" "$case_root/generation"
  export XDG_STATE_HOME="$case_root/state"
  export HOME_CONFIG='test-user@elsewhere' TEST_HOME_NAMES='test-user@elsewhere'
  export TEST_SYSTEM_NAMES=$'host-a\nhost-b' TEST_HOST=host-a
  TEST_USER=$(id -un) || return 1
  export TEST_USER TEST_HOME="$HOME"
  export TEST_EXPECTED="$case_root/generation" TEST_SYSTEM_EXPECTED="$case_root/generation"
  export TEST_LOG="$case_root/actions" TEST_DIFF_LOG="$case_root/diffs"
  export TEST_SOURCES="@a(ss) [@(ss) ('xkb','us'),@(ss) ('xkb','ara')]"
  export TEST_ACTIVE_SOURCES="[('xkb', 'us')]"
  unset NIXOS_CONFIG TEST_DIFF_EXPECTED TEST_RETARGET_LINK TEST_RETARGET_ON_DIFF
}

# An explicit Home output is independent of an ambiguous system selection.
(
  start_case selection
  selected=$(bash -c 'source scripts/config.sh; select_home; printf "%s" "$HOME_CONFIG"') || fail 'explicit Home selection'
  [[ "$selected" == "$HOME_CONFIG" ]] || fail 'wrong Home output selected'
  selected=$(bash -c 'unset HOME_CONFIG; source scripts/config.sh; select_home; printf "%s" "$HOME_CONFIG"') || fail 'sole Home selection'
  [[ "$selected" == "$TEST_HOME_NAMES" ]] || fail 'sole Home output not selected'
  selected=$(HOME_CONFIG='' NIXOS_CONFIG=host-a TEST_HOME_NAMES="$(id -un)@host-a"$'\n'"$(id -un)@elsewhere" \
    bash -c 'source scripts/config.sh; select_home; printf "%s" "$HOME_CONFIG"') || fail 'system-context Home selection'
  [[ "$selected" == "$(id -un)@host-a" ]] || fail 'selected system did not supply Home context'
  aliased_homes="$(id -un)@host-a"$'\n'"$(id -un)@alias"
  status=$(HOME_CONFIG='' NIXOS_CONFIG='' TEST_SYSTEM_NAMES=alias TEST_HOME_NAMES="$aliased_homes" \
    bash scripts/status.sh) || fail 'status with an implicitly selected system alias'
  grep -Fq "Home Manager ($(id -un)@host-a)" <<<"$status" || fail 'implicit system alias changed Home selection'
  status=$(HOME_CONFIG='' NIXOS_CONFIG=alias TEST_SYSTEM_NAMES=alias TEST_HOME_NAMES="$aliased_homes" \
    bash scripts/status.sh) || fail 'status with an explicitly selected system alias'
  grep -Fq "Home Manager ($(id -un)@host-a)" <<<"$status" || fail 'explicit system alias was mistaken for its hostname'
  status=$(HOME_CONFIG="$(id -un)@alias" NIXOS_CONFIG=alias TEST_SYSTEM_NAMES=alias TEST_HOME_NAMES="$aliased_homes" \
    bash scripts/status.sh) || fail 'status with an explicit Home output'
  grep -Fq "Home Manager ($(id -un)@alias)" <<<"$status" || fail 'explicit Home selection was ignored'
  HOME_CONFIG='' NIXOS_CONFIG=alias TEST_SYSTEM_NAMES=alias TEST_HOME_NAMES="$aliased_homes" \
    just home-preview >"$case_root/output" 2>&1 || fail 'Home preview with an explicitly selected system alias'
  [[ -L "$XDG_STATE_HOME/nixos/result-home-$(id -un)@host-a" ]] || fail 'Home preview built the output name instead of its hostname'
  if HOME_CONFIG='' NIXOS_CONFIG=alias TEST_SYSTEM_NAMES=alias TEST_HOST='' TEST_HOME_NAMES="$aliased_homes" \
    bash scripts/status.sh >"$case_root/output" 2>&1; then
    fail 'selected system with no hostname influenced Home selection'
  fi
  grep -Fq 'has no hostname' "$case_root/output" || fail 'missing system hostname was not explained'
)

# Missing, broken, or stale previews must never mutate the Home profile.
(
  start_case home-switch
  home_result="$XDG_STATE_HOME/nixos/result-home-$HOME_CONFIG"
  ln -s "$case_root/generation" "$home_result"

  rm "$home_result"
  ln -s "$case_root/generation" "$XDG_STATE_HOME/nixos/result-home"
  if bash scripts/home-switch.sh >"$case_root/output" 2>&1; then
    fail 'legacy shared Home build was activated'
  fi
  if bash scripts/home-switch.sh >"$case_root/output" 2>&1; then
    fail 'missing Home build was activated'
  fi
  ln -s "$case_root/missing-generation" "$home_result"
  if bash scripts/home-switch.sh >"$case_root/output" 2>&1; then
    fail 'broken Home build was activated'
  fi
  rm "$home_result"
  ln -s "$case_root/generation" "$home_result"
  export TEST_EXPECTED="$case_root/other-generation"
  if bash scripts/home-switch.sh >"$case_root/output" 2>&1; then
    fail 'stale Home build was activated'
  fi
  if bash scripts/home-preview.sh >"$case_root/output" 2>&1; then
    fail 'stale Home preview mixed build and settings'
  fi
  [[ ! -s "$TEST_LOG" ]] || fail 'stale Home build touched the profile'

  # A matching saved build must be the exact generation installed and activated.
  export TEST_EXPECTED="$case_root/generation"
  bash scripts/home-switch.sh || fail 'matching Home build was not activated'
  grep -Fxq "profile --profile $XDG_STATE_HOME/nix/profiles/home-manager --set $TEST_EXPECTED" "$TEST_LOG" || fail 'saved Home path not installed'
  grep -Fxq "activate $TEST_EXPECTED/activate --driver-version 1" "$TEST_LOG" || fail 'saved Home path not activated'
  [[ $(wc -l <"$TEST_LOG") -eq 2 ]] || fail 'unexpected extra Home switch action'
)

# A different user or home directory must not be compared or activated.
(
  start_case home-owner-user
  export TEST_USER=another-user
  if bash scripts/home-preview.sh >"$case_root/output" 2>&1; then
    fail 'Home preview compared another user with the caller'
  fi
  if just home-preview >"$case_root/output" 2>&1; then
    fail 'Home preview recipe compared another user with the caller'
  fi
  [[ ! -L "$XDG_STATE_HOME/nixos/result-home-$HOME_CONFIG" ]] || fail 'foreign Home preview built before checking ownership'
  if bash scripts/status.sh >"$case_root/output" 2>&1; then
    fail "status reported the caller as another user's active generation"
  fi
  grep -Fq 'belongs to another-user' "$case_root/output" || fail 'status did not explain the Home ownership mismatch'
  if grep -Fq 'Home Manager (' "$case_root/output"; then
    fail 'status displayed the caller as the foreign Home output'
  fi
  if bash scripts/home-switch.sh >"$case_root/output" 2>&1; then
    fail 'Home output for another user was activated'
  fi
  just home-build >"$case_root/output" 2>&1 || fail 'building another Home output requires caller ownership'
  [[ ! -s "$TEST_LOG" ]] || fail 'Home identity guard touched the profile'
)

(
  start_case home-owner-directory
  export TEST_HOME="$case_root/another-home"
  if bash scripts/home-preview.sh >"$case_root/output" 2>&1; then
    fail 'Home preview compared a different home directory with the caller'
  fi
  if just home-preview >"$case_root/output" 2>&1; then
    fail 'Home preview recipe compared a different home directory with the caller'
  fi
  [[ ! -L "$XDG_STATE_HOME/nixos/result-home-$HOME_CONFIG" ]] || fail 'Home preview built before checking the home directory'
  if bash scripts/status.sh >"$case_root/output" 2>&1; then
    fail 'status reported the caller as a different home directory'
  fi
  if bash scripts/home-switch.sh >"$case_root/output" 2>&1; then
    fail 'Home output for a different home directory was activated'
  fi
  [[ ! -s "$TEST_LOG" ]] || fail 'Home directory guard touched the profile'
)

# NixOS uses the same saved-build check while retaining its hostname guard.
(
  start_case system-switch
  export NIXOS_CONFIG=host-a
  ln -s "$case_root/generation" "$XDG_STATE_HOME/nixos/result-system"
  if just switch >"$case_root/output" 2>&1; then
    fail 'legacy shared NixOS build was activated'
  fi
  ln -s "$case_root/generation" "$XDG_STATE_HOME/nixos/result-system-host-a"
  export TEST_SYSTEM_EXPECTED="$case_root/other-generation"
  if just switch >"$case_root/output" 2>&1; then
    fail 'stale NixOS build was activated'
  fi
  [[ ! -s "$TEST_LOG" ]] || fail 'stale NixOS build touched the system'
  export TEST_SYSTEM_EXPECTED="$case_root/generation"
  just switch >"$case_root/output" 2>&1 || {
    cat "$case_root/output" >&2
    fail 'matching NixOS build'
  }
  grep -Fxq "system nixos-rebuild switch --no-reexec --store-path $TEST_SYSTEM_EXPECTED" "$TEST_LOG" || fail 'saved NixOS path not activated'
)

# A dconf-only input-source change is observable without activating or
# printing unrelated values (especially SOPS secrets).
(
  start_case home-settings
  ln -s "$case_root/generation" "$XDG_STATE_HOME/nixos/result-home-$HOME_CONFIG"
  settings=$(bash scripts/home-preview.sh) || fail 'Home settings preview'
  grep -Fq 'Managed home files:' <<<"$settings" || fail 'managed files missing from preview'
  grep -Fq 'No prior Home Manager profile' <<<"$settings" || fail 'initial profile not reported'
  grep -Fq "$TEST_SOURCES" <<<"$settings" || fail 'desired input sources missing'
  grep -Fq "$TEST_ACTIVE_SOURCES" <<<"$settings" || fail 'active input sources missing'
  [[ "$settings" != *'No longer managed:'* ]] || fail 'first Home preview invented a prior file'
  [[ "$settings" != *secret* ]] || fail 'settings preview exposed unrelated values'
  [[ ! -s "$TEST_LOG" ]] || fail 'settings preview activated a generation'
)

# Saved previews for different NixOS outputs must not replace one another.
(
  start_case system-outputs
  mkdir -p "$case_root/other-generation"
  export NIXOS_CONFIG=host-a TEST_HOST=host-a TEST_SYSTEM_EXPECTED="$case_root/generation"
  just build >"$case_root/output" 2>&1 || fail 'build system output A'
  export NIXOS_CONFIG=host-b TEST_HOST=host-b TEST_SYSTEM_EXPECTED="$case_root/other-generation"
  just build >"$case_root/output" 2>&1 || fail 'build system output B'
  export NIXOS_CONFIG=host-a TEST_HOST=host-a TEST_SYSTEM_EXPECTED="$case_root/generation"
  just switch >"$case_root/output" 2>&1 || fail 'saved system output A was replaced by B'
  grep -Fxq "system nixos-rebuild switch --no-reexec --store-path $TEST_SYSTEM_EXPECTED" "$TEST_LOG" || fail 'system output A activated the wrong build'
  export NIXOS_CONFIG=host-b TEST_HOST=host-b TEST_SYSTEM_EXPECTED="$case_root/other-generation"
  just switch >"$case_root/output" 2>&1 || fail 'saved system output B was replaced by A'
  grep -Fxq "system nixos-rebuild switch --no-reexec --store-path $TEST_SYSTEM_EXPECTED" "$TEST_LOG" || fail 'system output B activated the wrong build'

  actions_before=$(cat "$TEST_LOG")
  status=$(NIXOS_CONFIG=host-a TEST_SYSTEM_EXPECTED="$case_root/generation" bash scripts/status.sh) || fail 'status for system output A'
  grep -A2 -Fx 'NixOS (host-a)' <<<"$status" | grep -Fxq "  Saved preview build: $case_root/generation" || fail 'status ignored system output A'
  status=$(NIXOS_CONFIG=host-b TEST_SYSTEM_EXPECTED="$case_root/other-generation" bash scripts/status.sh) || fail 'status for system output B'
  grep -A2 -Fx 'NixOS (host-b)' <<<"$status" | grep -Fxq "  Saved preview build: $case_root/other-generation" || fail 'status ignored system output B'
  [[ $(cat "$TEST_LOG") == "$actions_before" ]] || fail 'status activated a generation'
)

# Saved previews for different Home outputs must not replace one another.
(
  start_case home-outputs
  cp -a "$case_root/generation" "$case_root/other-generation"
  export TEST_HOME_NAMES=$'test-user@elsewhere\ntest-user@host-b'
  export HOME_CONFIG=test-user@elsewhere TEST_EXPECTED="$case_root/generation"
  just home-build >"$case_root/output" 2>&1 || fail 'build Home output A'
  export HOME_CONFIG=test-user@host-b TEST_EXPECTED="$case_root/other-generation"
  just home-build >"$case_root/output" 2>&1 || fail 'build Home output B'
  export HOME_CONFIG=test-user@elsewhere TEST_EXPECTED="$case_root/generation"
  bash scripts/home-switch.sh >"$case_root/output" 2>&1 || fail 'saved Home output A was replaced by B'
  grep -Fxq "profile --profile $XDG_STATE_HOME/nix/profiles/home-manager --set $TEST_EXPECTED" "$TEST_LOG" || fail 'Home output A activated the wrong build'
  export HOME_CONFIG=test-user@host-b TEST_EXPECTED="$case_root/other-generation"
  bash scripts/home-switch.sh >"$case_root/output" 2>&1 || fail 'saved Home output B was replaced by A'
  grep -Fxq "profile --profile $XDG_STATE_HOME/nix/profiles/home-manager --set $TEST_EXPECTED" "$TEST_LOG" || fail 'Home output B activated the wrong build'

  actions_before=$(cat "$TEST_LOG")
  status=$(HOME_CONFIG=test-user@elsewhere TEST_EXPECTED="$case_root/generation" bash scripts/status.sh) || fail 'status for Home output A'
  grep -A2 -Fx 'Home Manager (test-user@elsewhere)' <<<"$status" | grep -Fxq "  Saved preview build: $case_root/generation" || fail 'status ignored Home output A'
  status=$(HOME_CONFIG=test-user@host-b TEST_EXPECTED="$case_root/other-generation" bash scripts/status.sh) || fail 'status for Home output B'
  grep -A2 -Fx 'Home Manager (test-user@host-b)' <<<"$status" | grep -Fxq "  Saved preview build: $case_root/other-generation" || fail 'status ignored Home output B'
  [[ $(cat "$TEST_LOG") == "$actions_before" ]] || fail 'status activated a Home generation'
)

# Status must not count a plain directory as a saved preview build, even when
# that directory matches the desired generation's path.
(
  start_case invalid-preview
  invalid_result="$XDG_STATE_HOME/nixos/result-home-test-user@elsewhere"
  mkdir "$invalid_result"
  status=$(HOME_CONFIG=test-user@elsewhere TEST_EXPECTED="$invalid_result" bash scripts/status.sh) || fail 'status for invalid Home preview'
  grep -Fq "  Saved preview build: not a symlink ($invalid_result)" <<<"$status" || fail 'status accepted a directory as a saved preview'
  grep -Fq 'State: neither active nor saved build matches the flake' <<<"$status" || fail 'invalid Home preview matched desired generation'
  ln -s "$invalid_result" "$XDG_STATE_HOME/nix/profiles/home-manager"
  status=$(HOME_CONFIG=test-user@elsewhere TEST_EXPECTED="$invalid_result" bash scripts/status.sh) || fail 'status with active generation and invalid saved preview'
  grep -Fq 'State: active matches the flake; saved build is missing/stale' <<<"$status" || fail 'active generation concealed an invalid saved preview'
  rm "$XDG_STATE_HOME/nix/profiles/home-manager"
  if HOME_CONFIG=test-user@elsewhere TEST_EXPECTED="$invalid_result" bash scripts/home-switch.sh >"$case_root/output" 2>&1; then
    fail 'plain directory was activated as a Home preview'
  fi
  [[ ! -s "$TEST_LOG" ]] || fail 'invalid Home preview touched the profile'
  rmdir "$invalid_result"
  ln -s "$case_root/missing-generation" "$invalid_result"
  status=$(HOME_CONFIG=test-user@elsewhere TEST_EXPECTED="$case_root/missing-generation" bash scripts/status.sh) || fail 'status for broken Home preview'
  grep -Fq "  Saved preview build: broken symlink ($invalid_result)" <<<"$status" || fail 'status accepted a broken saved preview'
  grep -Fq 'State: neither active nor saved build matches the flake' <<<"$status" || fail 'broken Home preview matched desired generation'
)

# Preview commands must compare the selected output's build, not a shared link.
(
  start_case pinned-previews
  cp -a "$case_root/generation" "$case_root/other-generation"
  export TEST_HOME_NAMES=$'test-user@elsewhere\ntest-user@host-b'
  export NIXOS_CONFIG=host-a TEST_HOST=host-a TEST_SYSTEM_EXPECTED="$case_root/generation" TEST_DIFF_EXPECTED="$case_root/generation"
  just preview >"$case_root/output" 2>&1 || fail 'preview system output A'
  export NIXOS_CONFIG=host-b TEST_HOST=host-b TEST_SYSTEM_EXPECTED="$case_root/other-generation" TEST_DIFF_EXPECTED="$case_root/other-generation"
  just preview >"$case_root/output" 2>&1 || fail 'preview system output B'
  ln -s "$case_root/generation" "$XDG_STATE_HOME/nix/profiles/home-manager"
  export HOME_CONFIG=test-user@host-b TEST_EXPECTED="$case_root/other-generation" TEST_DIFF_EXPECTED="$case_root/other-generation"
  just home-preview >"$case_root/output" 2>&1 || fail 'preview Home output B'
  [[ $(wc -l <"$TEST_DIFF_LOG") -eq 3 ]] || fail 'preview missed a closure comparison'
  [[ ! -s "$TEST_LOG" ]] || fail 'preview activated a generation'

  # Even if a saved link changes during a diff, both previews must report the
  # validated generation rather than following the link again.
  export NIXOS_CONFIG=host-a TEST_HOST=host-a TEST_SYSTEM_EXPECTED="$case_root/generation" TEST_DIFF_EXPECTED="$case_root/generation"
  export TEST_RETARGET_LINK="$XDG_STATE_HOME/nixos/result-system-host-a" TEST_RETARGET_ON_DIFF="$case_root/other-generation"
  just preview >"$case_root/output" 2>&1 || fail 'system preview followed a changed saved link'
  ln -sfn "$case_root/generation" "$TEST_RETARGET_LINK"

  ln -s "$case_root/only-in-saved-build" "$case_root/other-generation/home-files/pinned-only"
  export HOME_CONFIG=test-user@host-b TEST_EXPECTED="$case_root/other-generation" TEST_DIFF_EXPECTED="$case_root/other-generation"
  export TEST_RETARGET_LINK="$XDG_STATE_HOME/nixos/result-home-$HOME_CONFIG" TEST_RETARGET_ON_DIFF="$case_root/generation"
  preview=$(bash scripts/home-preview.sh) || fail 'Home preview followed a changed saved link'
  grep -Fq '  ~/pinned-only' <<<"$preview" || fail 'Home preview read files from a changed saved link'
)

# Compare the active profile's managed files with the saved build. A missing
# link is no longer managed, while a link retained in both must not be listed.
(
  start_case managed-files
  cp -a "$case_root/generation" "$case_root/other-generation"
  export HOME_CONFIG=test-user@host-b TEST_HOME_NAMES=$'test-user@elsewhere\ntest-user@host-b'
  export TEST_EXPECTED="$case_root/other-generation" TEST_DIFF_EXPECTED="$case_root/other-generation"
  ln -s "$case_root/generation" "$XDG_STATE_HOME/nix/profiles/home-manager"
  ln -s "$case_root/other-generation" "$XDG_STATE_HOME/nixos/result-home-$HOME_CONFIG"
  ln -s "$case_root/old-content" "$case_root/generation/home-files/removed"
  ln -s "$case_root/old-content" "$case_root/generation/home-files/kept"
  ln -s "$case_root/new-content" "$case_root/other-generation/home-files/kept"
  mkdir -p "$case_root/generation/home-files/.config/app" "$case_root/other-generation/home-files/.config/app"
  ln -s "$case_root/old-content" "$case_root/generation/home-files/.config/app/removed.conf"
  ln -s "$case_root/old-content" "$case_root/generation/home-files/.config/app/kept.conf"
  ln -s "$case_root/new-content" "$case_root/other-generation/home-files/.config/app/kept.conf"
  preview=$(bash scripts/home-preview.sh) || fail 'Home managed-file delta preview'
  grep -Fq 'No longer managed: ~/removed' <<<"$preview" || fail 'Home preview omitted a formerly managed file'
  grep -Fq 'No longer managed: ~/.config/app/removed.conf' <<<"$preview" || fail 'Home preview omitted a nested formerly managed file'
  [[ "$preview" != *'No longer managed: ~/kept'* ]] || fail 'Home preview marked a retained file as removed'
  [[ "$preview" != *'No longer managed: ~/.config/app/kept.conf'* ]] || fail 'Home preview marked a nested retained file as removed'
  preview=$(TEST_SOURCES='' bash scripts/home-preview.sh) || fail 'Home managed-file preview without GNOME sources'
  grep -Fq 'No longer managed: ~/.config/app/removed.conf' <<<"$preview" || fail 'GNOME-free Home preview omitted managed-file changes'
  grep -Fq 'No GNOME input sources declared by this Home output.' <<<"$preview" || fail 'GNOME-free Home preview omitted the settings notice'
)

# Equal desired paths do not let one output borrow another's saved preview.
(
  start_case equal-path-outputs
  export TEST_HOME_NAMES=$'test-user@elsewhere\ntest-user@host-b'
  ln -s "$case_root/generation" "$XDG_STATE_HOME/nixos/result-home-test-user@elsewhere"
  export HOME_CONFIG=test-user@host-b TEST_EXPECTED="$case_root/generation"
  if bash scripts/home-switch.sh >"$case_root/output" 2>&1; then
    fail 'Home output B borrowed another saved preview'
  fi
  [[ ! -s "$TEST_LOG" ]] || fail 'missing output-specific preview touched the profile'
  just home-build >"$case_root/output" 2>&1 || fail 'build Home output B with equal desired path'
  bash scripts/home-switch.sh >"$case_root/output" 2>&1 || fail 'Home output B cannot keep its own equal-path preview'
  grep -Fxq "profile --profile $XDG_STATE_HOME/nix/profiles/home-manager --set $TEST_EXPECTED" "$TEST_LOG" || fail 'Home output B did not install its own saved build'
  grep -Fxq "activate $TEST_EXPECTED/activate --driver-version 1" "$TEST_LOG" || fail 'Home output B did not activate its own saved build'
)

printf 'Workflow tests passed.\n'
