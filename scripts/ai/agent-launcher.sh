#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/logging.sh
source "${SCRIPT_DIR}/../lib/logging.sh"
# shellcheck source=scripts/lib/require.sh
source "${SCRIPT_DIR}/../lib/require.sh"
# shellcheck source=scripts/lib/fzf-theme.sh
source "${SCRIPT_DIR}/../lib/fzf-theme.sh"
# shellcheck source=scripts/ai/_agent-registry.sh
source "${SCRIPT_DIR}/_agent-registry.sh"

need_cmd fzf

usage() {
	echo "Usage: ai-agent-launcher [-s|--simple]"
	echo "  default: sectioned mode (provider -> profile/mode -> suffix)"
	echo "  -s, --simple: flat prefix picker mode"
}

# resolve_workflow_prompt and workflow_label are provided by _agent-registry.sh

workflow_display_lines() {
	echo "none"
	local suffix
	for suffix in "${WORKFLOW_SUFFIXES[@]}"; do
		workflow_label "$suffix"
	done
}

workflow_suffix_from_selection() {
	local selection="$1"
	if [[ "$selection" == "none" ]]; then
		echo "none"
		return 0
	fi

	local suffix
	for suffix in "${WORKFLOW_SUFFIXES[@]}"; do
		if [[ "$selection" == "$(workflow_label "$suffix")" ]]; then
			echo "$suffix"
			return 0
		fi
	done

	return 1
}

choose_workflow_suffix() {
	local base_alias="$1"
	local selection suffix

	if ! is_supported_base_alias "$base_alias"; then
		echo "none"
		return 0
	fi

	selection="$(workflow_display_lines | pick_lines "Select Workflow Suffix")"
	if [[ -z "${selection:-}" ]]; then
		return 1
	fi

	suffix="$(workflow_suffix_from_selection "$selection")" || return 1

	echo "$suffix"
}

# Execute a registered agent by looking up its config in the shared AGENT_REGISTRY.
execute_agent() {
	local agent_alias="$1"
	local workflow_suffix="$2"
	local prompt=""

	if [[ "$workflow_suffix" != "none" ]]; then
		prompt="$(resolve_workflow_prompt "$workflow_suffix")"
	fi

	if ! resolve_alias_entry AGENT_REGISTRY "$agent_alias"; then
		error_exit "Unsupported alias: $agent_alias"
	fi

	# Build command array for safe execution
	local -a cmd=()

	if [[ -n "$_RESOLVED_ENV" ]]; then
		# shellcheck disable=SC2206
		local -a env_args=($_RESOLVED_ENV)
		cmd+=(env "${env_args[@]}")
	fi

	# shellcheck disable=SC2206
	local -a prefix_args=($_COMMAND_PREFIX)
	cmd+=("${prefix_args[@]}")

	if [[ -n "$prompt" ]]; then
		if [[ "$_COMMAND_PREFIX" == opencode* ]]; then
			cmd+=("--prompt")
		fi
		cmd+=("$prompt")
	fi

	exec "${cmd[@]}"
}

# Generic effort alias picker: pick from fzf, map to alias.
# Args: $1=header $2=default_alias $3=low_alias $4=medium_alias $5=high_alias $6=xhigh_alias
_pick_effort_alias() {
	local header="$1"
	shift
	local default_alias="$1" low_alias="$2" med_alias="$3" high_alias="$4" xhigh_alias="$5"
	local effort
	effort="$(pick "$header" default low medium high xhigh)"
	case "$effort" in
	default) echo "$default_alias" ;;
	low) echo "$low_alias" ;;
	medium) echo "$med_alias" ;;
	high) echo "$high_alias" ;;
	xhigh) echo "$xhigh_alias" ;;
	"") return 1 ;;
	esac
}

pick_codex_effort_alias() {
	_pick_effort_alias "Codex Reasoning Effort" cx lcx mcx hcx xcx
}

pick_ocgpt_effort_alias() {
	_pick_effort_alias "OpenCode GPT Reasoning Effort" ocgpt locgpt mocgpt xocgpt xocgpt
}

run_simple_mode() {
	local agent_alias claude_mode

	agent_alias="$(pick "Simple Mode: Select Agent Prefix" "${LAUNCHER_SIMPLE_ALIASES[@]}")"
	if [[ -z "${agent_alias:-}" ]]; then
		return 1
	fi

	if [[ "$agent_alias" == "cl" ]]; then
		claude_mode="$(pick "Claude Model" default opus haiku)"
		case "$claude_mode" in
		default) agent_alias="cl" ;;
		opus) agent_alias="ocl" ;;
		haiku) agent_alias="hcl" ;;
		"") return 1 ;;
		esac
	fi

	case "$agent_alias" in
	cx | lcx | mcx | hcx | xcx)
		agent_alias="$(pick_codex_effort_alias)" || return 1
		;;
	esac

	case "$agent_alias" in
	ocgpt | locgpt | mocgpt | xocgpt)
		agent_alias="$(pick_ocgpt_effort_alias)" || return 1
		;;
	esac

	echo "$agent_alias"
}

run_sectioned_mode() {
	local provider_choice profile_choice mode_choice agent_alias

	provider_choice="$(pick "Select Provider" "OpenCode" "Claude Code" "Codex" "Gemini")"
	if [[ -z "${provider_choice:-}" ]]; then
		return 1
	fi

	case "$provider_choice" in
	"OpenCode")
		profile_choice="$(pick "OpenCode profile" default glm gemini gpt openrouter sonnet zen)"
		case "$profile_choice" in
		default) agent_alias="oc" ;;
		glm) agent_alias="ocglm" ;;
		gemini) agent_alias="ocgem" ;;
		gpt) agent_alias="$(pick_ocgpt_effort_alias)" || return 1 ;;
		openrouter) agent_alias="ocor" ;;
		sonnet) agent_alias="ocs" ;;
		zen) agent_alias="oczen" ;;
		"") return 1 ;;
		esac
		;;
	"Claude Code")
		mode_choice="$(pick "Claude Mode" default opus haiku glm)"
		case "$mode_choice" in
		default) agent_alias="cl" ;;
		opus) agent_alias="ocl" ;;
		haiku) agent_alias="hcl" ;;
		glm) agent_alias="clglm" ;;
		"") return 1 ;;
		esac
		;;
	"Codex")
		mode_choice="$(pick "Codex Mode" default yolo)"
		case "$mode_choice" in
		default) agent_alias="$(pick_codex_effort_alias)" || return 1 ;;
		yolo) agent_alias="cx" ;;
		"") return 1 ;;
		esac
		;;
	"Gemini")
		agent_alias="gem"
		;;
	esac

	echo "$agent_alias"
}

main() {
	local simple_mode=false
	while [[ $# -gt 0 ]]; do
		case "$1" in
		-s | --simple)
			simple_mode=true
			;;
		-h | --help)
			usage
			exit 0
			;;
		*)
			print_error "Unknown argument: $1"
			usage >&2
			exit 1
			;;
		esac
		shift
	done

	local agent_alias=""
	local workflow_suffix=""

	if [[ "$simple_mode" == true ]]; then
		agent_alias="$(run_simple_mode)" || exit 0
	else
		agent_alias="$(run_sectioned_mode)" || exit 0
	fi

	workflow_suffix="$(choose_workflow_suffix "$agent_alias")" || exit 0

	execute_agent "$agent_alias" "$workflow_suffix"
}

# Allow test scripts to source this file without executing main.
if [[ -z "${AI_AGENT_LAUNCHER_SOURCE_ONLY:-}" ]]; then
  main "$@"
fi
