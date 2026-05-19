#!/usr/bin/env bash
# Shared RE infrastructure: workspace resolution and common helpers.
# Used by both android-re and web-re domains.
# Source this file after sourcing logging.sh and require.sh.

# Resolve the niri workspace reference containing a pattern in its name.
# Prints the workspace ref (or fallback if niri is unavailable/no match).
resolve_niri_workspace() {
	local pattern="$1"
	local fallback="${2:-}"
	if ! command -v niri >/dev/null 2>&1; then
		printf '%s\n' "${fallback}"
		return 0
	fi
	local ref
	ref="$(niri msg workspaces 2>/dev/null | sed -n "s/.*\"\([^\"]*${pattern}[^\"]*\)\".*/\1/p" | head -n1)"
	if [[ -n "${ref}" ]]; then
		printf '%s\n' "${ref}"
	else
		printf '%s\n' "${fallback}"
	fi
}
