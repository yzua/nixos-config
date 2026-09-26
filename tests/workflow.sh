#!/usr/bin/env bash
# Exercise preview/switch commands without building or activating real generations.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

test_root=$(mktemp -d "${TMPDIR:-/tmp}/system-workflow-tests.XXXXXXXX")
trap 'rm -rf -- "$test_root"' EXIT
mkdir -p "$test_root/bin" "$test_root/state/nixos" "$test_root/state/nix/profiles" "$test_root/generation/home-files"

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
export XDG_STATE_HOME="$test_root/state"
export HOME_CONFIG='test-user@elsewhere'
export TEST_HOME_NAMES="$HOME_CONFIG"
export TEST_SYSTEM_NAMES=$'host-a\nhost-b'
TEST_USER=$(id -un)
export TEST_USER
export TEST_HOME="$HOME"
export TEST_EXPECTED="$test_root/generation"
export TEST_LOG="$test_root/log"
export TEST_DIFF_LOG="$test_root/diffs"
export TEST_SOURCES="@a(ss) [@(ss) ('xkb','us'),@(ss) ('xkb','ara')]"
export TEST_ACTIVE_SOURCES="[('xkb', 'us')]"
export TEST_HOST=host-a
export TEST_SYSTEM_EXPECTED="$test_root/generation"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

# An explicit Home output is independent of an ambiguous system selection.
selected=$(bash -c 'source scripts/config.sh; select_home; printf "%s" "$HOME_CONFIG"') || fail 'explicit Home selection'
[[ "$selected" == "$HOME_CONFIG" ]] || fail 'wrong Home output selected'
selected=$(bash -c 'unset HOME_CONFIG; source scripts/config.sh; select_home; printf "%s" "$HOME_CONFIG"') || fail 'sole Home selection'
[[ "$selected" == "$TEST_HOME_NAMES" ]] || fail 'sole Home output not selected'
selected=$(HOME_CONFIG='' NIXOS_CONFIG=host-a TEST_HOME_NAMES="$(id -un)@host-a"$'\n'"$(id -un)@elsewhere" \
  bash -c 'source scripts/config.sh; select_home; printf "%s" "$HOME_CONFIG"') || fail 'system-context Home selection'
[[ "$selected" == "$(id -un)@host-a" ]] || fail 'selected system did not supply Home context'

home_result="$XDG_STATE_HOME/nixos/result-home-$HOME_CONFIG"
ln -s "$test_root/generation" "$home_result"

# Missing, broken, or stale previews must never mutate the Home profile.
rm "$home_result"
ln -s "$test_root/generation" "$XDG_STATE_HOME/nixos/result-home"
if bash scripts/home-switch.sh >"$test_root/output" 2>&1; then
  fail 'legacy shared Home build was activated'
fi
if bash scripts/home-switch.sh >"$test_root/output" 2>&1; then
  fail 'missing Home build was activated'
fi
ln -s "$test_root/missing-generation" "$home_result"
if bash scripts/home-switch.sh >"$test_root/output" 2>&1; then
  fail 'broken Home build was activated'
fi
rm "$home_result"
ln -s "$test_root/generation" "$home_result"
export TEST_EXPECTED="$test_root/other-generation"
if bash scripts/home-switch.sh >"$test_root/output" 2>&1; then
  fail 'stale Home build was activated'
fi
if bash scripts/home-preview.sh >"$test_root/output" 2>&1; then
  fail 'stale Home preview mixed build and settings'
fi
[[ ! -e "$TEST_LOG" ]] || fail 'stale Home build touched the profile'

# A matching saved build must be the exact generation installed and activated.
export TEST_EXPECTED="$test_root/generation"
bash scripts/home-switch.sh || fail 'matching Home build was not activated'
grep -Fxq "profile --profile $XDG_STATE_HOME/nix/profiles/home-manager --set $TEST_EXPECTED" "$TEST_LOG" || fail 'saved Home path not installed'
grep -Fxq "activate $TEST_EXPECTED/activate --driver-version 1" "$TEST_LOG" || fail 'saved Home path not activated'
[[ $(wc -l <"$TEST_LOG") -eq 2 ]] || fail 'unexpected extra Home switch action'

export TEST_USER=another-user
if bash scripts/home-switch.sh >"$test_root/output" 2>&1; then
  fail 'Home output for another user was activated'
fi
[[ $(wc -l <"$TEST_LOG") -eq 2 ]] || fail 'Home identity guard touched the profile'
TEST_USER=$(id -un)
export TEST_USER

# NixOS uses the same saved-build check while retaining its hostname guard.
export NIXOS_CONFIG=host-a
ln -s "$test_root/generation" "$XDG_STATE_HOME/nixos/result-system"
if just switch >"$test_root/output" 2>&1; then
  fail 'legacy shared NixOS build was activated'
fi
ln -s "$test_root/generation" "$XDG_STATE_HOME/nixos/result-system-host-a"
export TEST_SYSTEM_EXPECTED="$test_root/other-generation"
if just switch >"$test_root/output" 2>&1; then
  fail 'stale NixOS build was activated'
fi
[[ $(wc -l <"$TEST_LOG") -eq 2 ]] || fail 'stale NixOS build touched the system'
export TEST_SYSTEM_EXPECTED="$test_root/generation"
just switch >"$test_root/output" 2>&1 || {
  cat "$test_root/output" >&2
  fail 'matching NixOS build'
}
grep -Fxq "system nixos-rebuild switch --no-reexec --store-path $TEST_SYSTEM_EXPECTED" "$TEST_LOG" || fail 'saved NixOS path not activated'

# A dconf-only input-source change is observable without activating or
# printing unrelated values (especially SOPS secrets).
settings=$(bash scripts/home-preview.sh) || fail 'Home settings preview'
grep -Fq 'Managed home files:' <<<"$settings" || fail 'managed files missing from preview'
grep -Fq 'No prior Home Manager profile' <<<"$settings" || fail 'initial profile not reported'
grep -Fq "$TEST_SOURCES" <<<"$settings" || fail 'desired input sources missing'
grep -Fq "$TEST_ACTIVE_SOURCES" <<<"$settings" || fail 'active input sources missing'
[[ "$settings" != *secret* ]] || fail 'settings preview exposed unrelated values'
[[ $(wc -l <"$TEST_LOG") -eq 3 ]] || fail 'settings preview activated a generation'

# Saved previews for different NixOS outputs must not replace one another.
mkdir -p "$test_root/other-generation"
export NIXOS_CONFIG=host-a TEST_HOST=host-a TEST_SYSTEM_EXPECTED="$test_root/generation"
just build >"$test_root/output" 2>&1 || fail 'build system output A'
export NIXOS_CONFIG=host-b TEST_HOST=host-b TEST_SYSTEM_EXPECTED="$test_root/other-generation"
just build >"$test_root/output" 2>&1 || fail 'build system output B'
export NIXOS_CONFIG=host-a TEST_HOST=host-a TEST_SYSTEM_EXPECTED="$test_root/generation"
just switch >"$test_root/output" 2>&1 || fail 'saved system output A was replaced by B'
grep -Fxq "system nixos-rebuild switch --no-reexec --store-path $TEST_SYSTEM_EXPECTED" "$TEST_LOG" || fail 'system output A activated the wrong build'
export NIXOS_CONFIG=host-b TEST_HOST=host-b TEST_SYSTEM_EXPECTED="$test_root/other-generation"
just switch >"$test_root/output" 2>&1 || fail 'saved system output B was replaced by A'
grep -Fxq "system nixos-rebuild switch --no-reexec --store-path $TEST_SYSTEM_EXPECTED" "$TEST_LOG" || fail 'system output B activated the wrong build'

status=$(NIXOS_CONFIG=host-a TEST_SYSTEM_EXPECTED="$test_root/generation" bash scripts/status.sh) || fail 'status for system output A'
grep -A2 -Fx 'NixOS (host-a)' <<<"$status" | grep -Fxq "  Saved preview build: $test_root/generation" || fail 'status ignored system output A'
status=$(NIXOS_CONFIG=host-b TEST_SYSTEM_EXPECTED="$test_root/other-generation" bash scripts/status.sh) || fail 'status for system output B'
grep -A2 -Fx 'NixOS (host-b)' <<<"$status" | grep -Fxq "  Saved preview build: $test_root/other-generation" || fail 'status ignored system output B'
[[ $(wc -l <"$TEST_LOG") -eq 5 ]] || fail 'status activated a generation'

# Saved previews for different Home outputs must not replace one another.
cp -a "$test_root/generation/." "$test_root/other-generation/"
export TEST_HOME_NAMES=$'test-user@elsewhere\ntest-user@host-b'
export HOME_CONFIG=test-user@elsewhere TEST_EXPECTED="$test_root/generation"
just home-build >"$test_root/output" 2>&1 || fail 'build Home output A'
export HOME_CONFIG=test-user@host-b TEST_EXPECTED="$test_root/other-generation"
just home-build >"$test_root/output" 2>&1 || fail 'build Home output B'
export HOME_CONFIG=test-user@elsewhere TEST_EXPECTED="$test_root/generation"
bash scripts/home-switch.sh >"$test_root/output" 2>&1 || fail 'saved Home output A was replaced by B'
grep -Fxq "profile --profile $XDG_STATE_HOME/nix/profiles/home-manager --set $TEST_EXPECTED" "$TEST_LOG" || fail 'Home output A activated the wrong build'
export HOME_CONFIG=test-user@host-b TEST_EXPECTED="$test_root/other-generation"
bash scripts/home-switch.sh >"$test_root/output" 2>&1 || fail 'saved Home output B was replaced by A'
grep -Fxq "profile --profile $XDG_STATE_HOME/nix/profiles/home-manager --set $TEST_EXPECTED" "$TEST_LOG" || fail 'Home output B activated the wrong build'

status=$(HOME_CONFIG=test-user@elsewhere TEST_EXPECTED="$test_root/generation" bash scripts/status.sh) || fail 'status for Home output A'
grep -A2 -Fx 'Home Manager (test-user@elsewhere)' <<<"$status" | grep -Fxq "  Saved preview build: $test_root/generation" || fail 'status ignored Home output A'
status=$(HOME_CONFIG=test-user@host-b TEST_EXPECTED="$test_root/other-generation" bash scripts/status.sh) || fail 'status for Home output B'
grep -A2 -Fx 'Home Manager (test-user@host-b)' <<<"$status" | grep -Fxq "  Saved preview build: $test_root/other-generation" || fail 'status ignored Home output B'
[[ $(wc -l <"$TEST_LOG") -eq 9 ]] || fail 'status activated a Home generation'

# Preview commands must compare the selected output's build, not a shared link.
export NIXOS_CONFIG=host-a TEST_HOST=host-a TEST_SYSTEM_EXPECTED="$test_root/generation" TEST_DIFF_EXPECTED="$test_root/generation"
just preview >"$test_root/output" 2>&1 || fail 'preview system output A'
export NIXOS_CONFIG=host-b TEST_HOST=host-b TEST_SYSTEM_EXPECTED="$test_root/other-generation" TEST_DIFF_EXPECTED="$test_root/other-generation"
just preview >"$test_root/output" 2>&1 || fail 'preview system output B'
ln -s "$test_root/generation" "$XDG_STATE_HOME/nix/profiles/home-manager"
export HOME_CONFIG=test-user@host-b TEST_EXPECTED="$test_root/other-generation" TEST_DIFF_EXPECTED="$test_root/other-generation"
just home-preview >"$test_root/output" 2>&1 || fail 'preview Home output B'
[[ $(wc -l <"$TEST_DIFF_LOG") -eq 3 ]] || fail 'preview missed a closure comparison'
[[ $(wc -l <"$TEST_LOG") -eq 9 ]] || fail 'preview activated a generation'

# Equal desired paths do not let one output borrow another's saved preview.
rm "$XDG_STATE_HOME/nixos/result-home-test-user@host-b"
export HOME_CONFIG=test-user@host-b TEST_EXPECTED="$test_root/generation"
if bash scripts/home-switch.sh >"$test_root/output" 2>&1; then
  fail 'Home output B borrowed another saved preview'
fi
[[ $(wc -l <"$TEST_LOG") -eq 9 ]] || fail 'missing output-specific preview touched the profile'
just home-build >"$test_root/output" 2>&1 || fail 'build Home output B with equal desired path'
bash scripts/home-switch.sh >"$test_root/output" 2>&1 || fail 'Home output B cannot keep its own equal-path preview'
[[ $(wc -l <"$TEST_LOG") -eq 11 ]] || fail 'Home output B did not activate its own saved build'

printf 'Workflow tests passed.\n'
