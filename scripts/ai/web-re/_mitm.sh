#!/usr/bin/env bash
# MITM proxy (mitmproxy) setup and configuration for web RE.
# shellcheck source=scripts/lib/logging.sh
# shellcheck source=scripts/ai/web-re/_helpers.sh
# shellcheck source=scripts/ai/_re-mitm-common.sh

MITM_CONF_DIR="${MITM_CONF_DIR:-${HOME}/Downloads/web-re-tools/custom-ca}"
MITM_HOST="${MITM_HOST:-0.0.0.0}"
MITM_PORT="${MITM_PORT:-8084}"

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/ai/_re-mitm-common.sh"

mitm_start() {
	need_cmd mitmdump
	mitm_ensure_ca_cert || return 1

	kill_mitm_listeners

	if mitm_running; then
		log_success "mitmproxy listener already present on ${MITM_PORT}"
		return 0
	fi

	# Start mitmdump in tmux if available, otherwise background
	if command -v tmux >/dev/null 2>&1 && tmux has-session -t "${TMUX_SESSION:-web-re}" 2>/dev/null; then
		tmux send-keys -t "${TMUX_SESSION:-web-re}:${TMUX_MITM_WINDOW:-mitm}" C-c
		tmux send-keys -t "${TMUX_SESSION:-web-re}:${TMUX_MITM_WINDOW:-mitm}" "clear"
		tmux send-keys -t "${TMUX_SESSION:-web-re}:${TMUX_MITM_WINDOW:-mitm}" Enter
		tmux send-keys -t "${TMUX_SESSION:-web-re}:${TMUX_MITM_WINDOW:-mitm}" "$(mitm_command)"
		tmux send-keys -t "${TMUX_SESSION:-web-re}:${TMUX_MITM_WINDOW:-mitm}" Enter
	else
		nohup "$(mitm_command)" >/dev/null 2>&1 &
		disown 2>/dev/null || true
	fi

	for _ in $(seq 1 15); do
		if mitm_running; then
			log_success "mitmproxy listening on ${MITM_HOST}:${MITM_PORT}"
			return 0
		fi
		sleep 1
	done

	error_exit "mitmproxy did not start on port ${MITM_PORT}"
}

mitm_stop() {
	kill_mitm_listeners
	log_success "mitmproxy stopped"
}
