# shellcheck shell=bash
# Shared log directory paths and discovery for AI agent scripts.
# Source this file to get consistent log directory constants and helpers.
# Usage: source "${SCRIPT_DIR}/../lib/log-dirs.sh"

# shellcheck disable=SC2034
LOG_DIR="${AI_AGENT_LOG_DIR:-$HOME/.local/share/ai-agents/logs}"
# shellcheck disable=SC2034
OPENCODE_LOG_DIR="${OPENCODE_LOG_DIR:-$HOME/.local/share/opencode/log}"
# shellcheck disable=SC2034
CODEX_LOG_DIR="${CODEX_LOG_DIR:-$HOME/.codex/log}"

# Add a root to seen_roots if not already present. Returns 0 (continue) or 1 (skip).
# Args: $1 — root path to check
# Modifies: seen_roots (caller must declare local -a seen_roots=())
_add_unique_root() {
	local root="$1"
	local prev
	for prev in "${seen_roots[@]}"; do
		[[ "$root" == "$prev" ]] && return 1
	done
	seen_roots+=("$root")
	return 0
}

# Core log discovery across a list of root directories.
# Args: $1 — mtime filter (default: -7)
#       remaining args — root directories to scan
# Output: sorted unique list of log file paths
_find_logs_in_roots() {
	local mtime="$1"
	shift
	local root
	local -a seen_roots=()
	local max_depth_args=()

	for root in "$@"; do
		[[ -d "$root" ]] || continue
		_add_unique_root "$root" || continue
		if [[ "$root" == "$LOG_DIR" ]]; then
			max_depth_args=(-maxdepth 1)
		else
			max_depth_args=()
		fi
		find "$root" "${max_depth_args[@]}" -type f -name '*.log' -mtime "$mtime" 2>/dev/null
	done | sort -u
}

# Print the canonical list of agent log root directories (one per line).
# Only includes directories that actually exist on disk.
# Use this when you need the directory paths themselves, not the log files.
agent_log_roots() {
	local root
	local -a seen_roots=()
	for root in "$LOG_DIR" "$OPENCODE_LOG_DIR" "$CODEX_LOG_DIR"; do
		[[ -d "$root" ]] || continue
		_add_unique_root "$root" || continue
		echo "$root"
	done
}

# Find all agent log files across standard directories.
# Args: $1 — mtime filter (default: -7, i.e. last 7 days)
# Output: sorted unique list of log file paths
find_all_agent_logs() {
	local mtime="${1:--7}"
	_find_logs_in_roots "$mtime" "$LOG_DIR" "$OPENCODE_LOG_DIR" "$CODEX_LOG_DIR"
}

# Find log files for a specific agent by name.
# Args: $1 — agent name (claude, opencode, codex, antigravity)
#        $2 — mtime filter (default: -7)
find_agent_logs() {
	local agent="$1"
	local mtime="${2:--7}"

	case "$agent" in
	claude | antigravity)
		_find_logs_in_roots "$mtime" "$LOG_DIR"
		;;
	opencode)
		_find_logs_in_roots "$mtime" "$LOG_DIR" "$OPENCODE_LOG_DIR"
		;;
	codex)
		_find_logs_in_roots "$mtime" "$LOG_DIR" "$CODEX_LOG_DIR"
		;;
	esac
}
