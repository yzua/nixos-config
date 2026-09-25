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

ln -s "$test_root/generation" "$XDG_STATE_HOME/nixos/result-home"

# Missing, broken, or stale previews must never mutate the Home profile.
rm "$XDG_STATE_HOME/nixos/result-home"
if bash scripts/home-switch.sh >"$test_root/output" 2>&1; then
  fail 'missing Home build was activated'
fi
ln -s "$test_root/missing-generation" "$XDG_STATE_HOME/nixos/result-home"
if bash scripts/home-switch.sh >"$test_root/output" 2>&1; then
  fail 'broken Home build was activated'
fi
rm "$XDG_STATE_HOME/nixos/result-home"
ln -s "$test_root/generation" "$XDG_STATE_HOME/nixos/result-home"
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
ln -s "$test_root/generation" "$XDG_STATE_HOME/nixos/result-system"
export NIXOS_CONFIG=host-a
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

printf 'Workflow tests passed.\n'
