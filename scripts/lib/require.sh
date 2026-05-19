#!/usr/bin/env bash
# Shared command/file requirement helpers.
# Source this file after sourcing logging.sh.

if [[ "$(type -t log_error)" != "function" ]]; then
  echo "require.sh: must be sourced after logging.sh" >&2
  # shellcheck disable=SC2317
  return 1 2>/dev/null || exit 1
fi

error_exit() {
	log_error "$1"
	exit "${2:-1}"
}

need_cmd() {
	local name="$1"
	command -v "$name" >/dev/null 2>&1 || error_exit "missing command: ${name}"
}

need_file() {
	local path="$1"
	[[ -e "$path" ]] || error_exit "missing file: ${path}"
}

# Check tool availability and report status (does not exit on missing).
check_tool() {
	local tool="$1"
	if command -v "$tool" >/dev/null 2>&1; then
		log_success "tool present: ${tool} -> $(command -v "$tool")"
	else
		log_warning "tool missing: ${tool}"
	fi
}

# Check whether a TCP port has an active listener on the host.
port_in_use() {
	local port="$1"
	command -v ss >/dev/null 2>&1 && ss -ltnH "( sport = :${port} )" | grep -q .
}
