#!/usr/bin/env bash
# Shared helper functions for web RE scripts.
# Source this file after sourcing logging.sh.

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/lib/require.sh"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/ai/_re-common.sh"

CHROME_DEBUG_PORT="${CHROME_DEBUG_PORT:-9222}"
CHROME_PROFILE_DIR="${CHROME_PROFILE_DIR:-${HOME}/.cache/web-re-tools/chrome-profile}"

# Check whether Chrome with remote debugging is running.
chrome_running() {
	port_in_use "${CHROME_DEBUG_PORT}"
}

# Resolve the niri workspace reference containing "web-re" in its name.
resolve_niri_web_re_workspace() { resolve_niri_workspace "web-re" "${1:-}"; }
