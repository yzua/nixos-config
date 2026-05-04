#!/usr/bin/env bash
# Shared workspace initialization helpers for RE adapters.
# Source this file after sourcing logging.sh and domain helpers.

# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/ai/_findings-schema.sh"

write_template() {
	local path="$1"
	shift
	if [[ -f "${path}" ]]; then
		log_info "already exists: $(basename "${path}")"
		return 0
	fi
	cat >"${path}" "$@"
	log_info "created $(basename "${path}")"
}

init_findings_database() {
	local workspace="$1"
	local schema_kind="$2"

	if [[ -f "${workspace}/findings.db" ]]; then
		log_info "findings database already exists: findings.db"
		return 0
	fi

	findings_schema_sql "${schema_kind}" | sqlite3 "${workspace}/findings.db"
	log_info "created findings.db"
}

init_exploitation_queue() {
	local workspace="$1"
	write_template "${workspace}/exploitation_queue.json" <<'QUEUE'
{"queue":[],"metadata":{"target":"","created":"","last_updated":""}}
QUEUE
}

init_workspace_git() {
	local workspace="$1"

	if [[ -d "${workspace}/.git" ]]; then
		log_info "git repository already initialized"
		return 0
	fi

	git init "${workspace}" >/dev/null 2>&1
	write_template "${workspace}/.gitignore" <<'GITIGNORE'
evidence/screenshots/
evidence/pcaps/
*.pcap
*.pcapng
*.har
GITIGNORE
	git -C "${workspace}" add -A >/dev/null 2>&1
	git -C "${workspace}" commit -m "workspace init" --quiet >/dev/null 2>&1 || true
	log_info "git repository initialized with checkpoint"
}
