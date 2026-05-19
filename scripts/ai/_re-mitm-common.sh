#!/usr/bin/env bash
# Shared MITM proxy (mitmproxy) infrastructure for RE domains.
# Used by both android-re and web-re domains.
# Source this file after sourcing logging.sh and require.sh.
# Requires: MITM_CONF_DIR, MITM_HOST, MITM_PORT to be set before sourcing.

# Kill any mitmproxy/mitmdump listeners on MITM_PORT.
kill_mitm_listeners() {
	pkill -f "mitmdump.*--listen-port ${MITM_PORT}" 2>/dev/null || true
	pkill -f "mitmproxy.*--listen-port ${MITM_PORT}" 2>/dev/null || true

	for _ in $(seq 1 10); do
		if ! port_in_use "${MITM_PORT}"; then
			return 0
		fi
		sleep 0.5
	done

	if port_in_use "${MITM_PORT}"; then
		log_warning "port ${MITM_PORT} still has a listener after mitm cleanup — killing forcefully"
		ss -ltnpH "( sport = :${MITM_PORT} )" | grep -oP 'pid=\K[0-9]+' | xargs -r kill -9 2>/dev/null || true
		sleep 1
	fi
}

# Print the mitmdump command line with current config.
mitm_command() {
	printf 'mitmdump --set confdir=%q --listen-host %q --listen-port %q --set ssl_insecure=true --set flow_detail=2' "${MITM_CONF_DIR}" "${MITM_HOST}" "${MITM_PORT}"
}

# Check if mitmproxy is listening on MITM_PORT.
mitm_running() {
	port_in_use "${MITM_PORT}"
}

# Generate mitmproxy CA cert if not already present.
mitm_ensure_ca_cert() {
	if [[ ! -e "${MITM_CONF_DIR}/mitmproxy-ca-cert.cer" ]]; then
		log_info "generating mitmproxy CA cert in ${MITM_CONF_DIR}"
		mkdir -p "${MITM_CONF_DIR}"
		mitmdump --set confdir="${MITM_CONF_DIR}" -q &
		local mitm_pid=$!
		sleep 3
		kill "${mitm_pid}" 2>/dev/null || true
		wait "${mitm_pid}" 2>/dev/null || true
		if [[ ! -e "${MITM_CONF_DIR}/mitmproxy-ca-cert.cer" ]]; then
			log_warning "failed to generate mitmproxy CA cert in ${MITM_CONF_DIR}"
			return 1
		fi
		log_success "mitmproxy CA cert generated"
	fi
}
