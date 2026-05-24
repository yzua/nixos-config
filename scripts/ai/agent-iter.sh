#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/logging.sh
source "${SCRIPT_DIR}/../lib/logging.sh"
# shellcheck source=scripts/lib/require.sh
source "${SCRIPT_DIR}/../lib/require.sh"
# shellcheck source=scripts/ai/_agent-registry.sh
source "${SCRIPT_DIR}/_agent-registry.sh"

usage() {
	cat <<'EOF'
Usage: iter [count] <agent-alias> [prompt...]

Examples:
  iter clglmmd
  iter 3 oc "fix the failing check"
  iter 5 ag "review this repo again"

Notes:
  - iter is headless/non-interactive. It will not open a persistent TUI.
  - Provide a prompt explicitly, or use a workflow alias like occm / clglmmd.
EOF
}

# require_secret_file provided by _agent-registry.sh

# zai_key_path provided by _agent-registry.sh

# is_supported_base_alias provided by _agent-registry.sh

# split_alias_suffix provided by _agent-registry.sh

# resolve_workflow_prompt provided by _agent-registry.sh

collect_prompt() {
	if [[ $# -eq 0 ]]; then
		printf '%s\n' ""
		return 0
	fi

	if [[ "$1" == "--prompt" ]]; then
		shift
	fi

	printf '%s\n' "$*"
}

# Check if stderr output indicates a rate-limit (transient) error.
# Matches: 429 status codes, "Rate limit", "Too Many Requests", etc.
is_rate_limit_error() {
	local output="$1"
	[[ "$output" =~ (429|Rate[_ ]limit|rate[_ ]limit|Too[_ ]Many[_ ]Requests|overloaded|capacity) ]]
}

# Run a single headless iteration of an agent using AGENT_ITER_REGISTRY.
# Returns 0 on success, 2 on rate-limit error (stderr captured in _ITER_LAST_STDERR),
# or the agent's raw exit code for other failures.
run_agent_once() {
	local alias_name="$1"
	local prompt="$2"

	if ! resolve_alias_entry AGENT_ITER_REGISTRY "$alias_name"; then
		error_exit "Unsupported alias for iter: ${alias_name}"
	fi

	local stderr_file
	stderr_file="$(mktemp)"
	trap 'rm -f "${stderr_file}"' RETURN

	local rc=0
	# Execute with resolved env, capturing stderr for rate-limit detection
	if [[ -n "$_RESOLVED_ENV" ]]; then
		# shellcheck disable=SC2086,SC2046
		env $_RESOLVED_ENV $_COMMAND_PREFIX "${prompt}" 2>"${stderr_file}" || rc=$?
	else
		# shellcheck disable=SC2086
		$_COMMAND_PREFIX "${prompt}" 2>"${stderr_file}" || rc=$?
	fi

	_ITER_LAST_STDERR="$(cat "${stderr_file}")"

	if ((rc != 0)) && is_rate_limit_error "${_ITER_LAST_STDERR}"; then
		trap - RETURN
		return 2
	fi
	trap - RETURN
	return "${rc}"
}

main() {
	if [[ $# -eq 0 ]]; then
		usage
		exit 1
	fi

	iteration_limit="unlimited"
	if [[ "$1" =~ ^[1-9][0-9]*$ ]]; then
		iteration_limit="$1"
		shift
	fi

	if [[ $# -eq 0 ]]; then
		usage
		exit 1
	fi

	alias_spec="$(split_alias_suffix "$1")"
	agent_alias="${alias_spec%%|*}"
	workflow_suffix="${alias_spec#*|}"
	shift

	if ! is_supported_base_alias "${agent_alias}"; then
		error_exit "Unsupported alias for iter: ${agent_alias}"
	fi

	workflow_prompt="$(resolve_workflow_prompt "${workflow_suffix}")"
	explicit_prompt="$(collect_prompt "$@")"

	if [[ -n "${workflow_prompt}" && -n "${explicit_prompt}" ]]; then
		error_exit "${agent_alias}${workflow_suffix} already includes a workflow prompt; do not pass another prompt"
	fi

	prompt="${explicit_prompt:-${workflow_prompt}}"
	if [[ -z "${prompt}" ]]; then
		error_exit "${agent_alias} requires a prompt or workflow alias"
	fi

	local rate_limit_retries="${ITER_RATE_LIMIT_RETRIES:-5}"
	local rate_limit_base_wait="${ITER_RATE_LIMIT_BASE_WAIT:-10}"
	local iteration=1
	local rate_limit_attempts=0

	while true; do
		print_info "Iteration ${iteration}/${iteration_limit}"
		if run_agent_once "${agent_alias}" "${prompt}"; then
			rate_limit_attempts=0
			if [[ "${iteration_limit}" != "unlimited" ]] && ((iteration >= iteration_limit)); then
				break
			fi
			iteration=$((iteration + 1))
			continue
		else
			status=$?
		fi

		if ((status == 2)); then
			rate_limit_attempts=$((rate_limit_attempts + 1))
			if ((rate_limit_attempts > rate_limit_retries)); then
				print_error "Rate-limit retry limit (${rate_limit_retries}) exceeded"
				error_exit "Iteration ${iteration}/${iteration_limit} failed with exit code ${status}" "${status}"
			fi
			wait_secs=$((rate_limit_base_wait * (2 ** (rate_limit_attempts - 1))))
			print_warning "Rate limit hit (attempt ${rate_limit_attempts}/${rate_limit_retries}), retrying in ${wait_secs}s..."
			sleep "${wait_secs}"
			continue
		fi

		error_exit "Iteration ${iteration}/${iteration_limit} failed with exit code ${status}" "${status}"
	done

	print_success "Completed ${iteration}/${iteration_limit} iterations"
}

# Allow test scripts to source this file without executing main.
if [[ -z "${AI_AGENT_ITER_SOURCE_ONLY:-}" ]]; then
  main "$@"
fi
