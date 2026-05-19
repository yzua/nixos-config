#!/usr/bin/env bash
# Shared helper functions for Android RE scripts.
# Source this file after sourcing logging.sh.

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/lib/require.sh"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/ai/_re-common.sh"

# Run an adb command, requiring adb to be available.
adb_run() {
	need_cmd adb
	adb "$@"
}

# Run an adb shell command and strip Windows-style carriage returns.
# Always returns success — intended for property reads and queries where
# failure should be non-fatal.
adb_prop() { adb shell "$@" 2>/dev/null | tr -d '\r' || true; }

# Check whether an Android emulator device is currently online.
emulator_online() { adb devices 2>/dev/null | grep -q '^emulator-'; }

# Resolve the niri workspace reference containing "android" in its name.
resolve_niri_android_workspace() { resolve_niri_workspace "android" "${1:-}"; }
