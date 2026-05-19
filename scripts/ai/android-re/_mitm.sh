#!/usr/bin/env bash
# MITM proxy (mitmproxy) setup, CA injection, and proxy configuration.
# shellcheck source=scripts/lib/logging.sh
# shellcheck source=scripts/ai/android-re/_helpers.sh
# shellcheck source=scripts/ai/_re-mitm-common.sh

MITM_CONF_DIR="${MITM_CONF_DIR:-${HOME}/Downloads/android-re-tools/custom-ca}"
MITM_CA_HASH="${MITM_CA_HASH:-}"
MITM_CA_SOURCE="${MITM_CA_SOURCE:-${MITM_CONF_DIR}/mitmproxy-ca-cert.cer}"
MITM_CA_TARGET=""
MITM_HOST="${MITM_HOST:-0.0.0.0}"
MITM_PORT="${MITM_PORT:-8084}"

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/ai/_re-mitm-common.sh"

# Internal: compute the CA certificate hash and set MITM_CA_HASH/MITM_CA_TARGET.
# Returns 0 on success, 1 on any failure (bad hash, openssl error).
_compute_ca_hash() {
	local cert_hash
	cert_hash="$(
		openssl x509 -inform PEM -subject_hash_old -in "${MITM_CA_SOURCE}" -noout 2>/dev/null ||
			openssl x509 -subject_hash_old -in "${MITM_CA_SOURCE}" -noout 2>/dev/null
	)" || return 1
	[[ -n "${cert_hash}" ]] || return 1
	if [[ -z "${MITM_CA_HASH}" ]]; then
		MITM_CA_HASH="${cert_hash}.0"
	fi
	MITM_CA_TARGET="/system/etc/security/cacerts/${MITM_CA_HASH}"
}

init_mitm_ca_vars() {
	# Lazy-init: skip if already resolved
	[[ -n "${MITM_CA_TARGET}" ]] && return 0

	need_cmd openssl
	need_file "${MITM_CA_SOURCE}"
	_compute_ca_hash || error_exit "failed to derive certificate hash from ${MITM_CA_SOURCE}"
}

# Non-fatal variant for diagnostic commands (status, doctor).
# Returns 1 on missing tools/files instead of calling error_exit.
_try_init_mitm_ca_vars() {
	[[ -n "${MITM_CA_TARGET}" ]] && return 0
	command -v openssl >/dev/null 2>&1 || return 1
	[[ -e "${MITM_CA_SOURCE}" ]] || return 1
	_compute_ca_hash || return 1
}

# Legacy alias for mitm_running from shared mitm common.
mitm_listener_ready() { mitm_running; }

sync_mitm_ca() {
	local device_cert
	init_mitm_ca_vars
	device_cert="/data/local/tmp/${MITM_CA_HASH}"

	adb_run push "${MITM_CA_SOURCE}" "${device_cert}" >/dev/null
	adb_run shell "su 0 sh -s" <<EOF
set -e
device_cert=${device_cert@Q}
tmp_copy='/data/local/tmp/tmp-ca-copy'
system_ca_dir='/system/etc/security/cacerts'
conscrypt_ca_dir='/apex/com.android.conscrypt/cacerts'

rm -rf "\$tmp_copy"
mkdir -p -m 700 "\$tmp_copy"
cp /apex/com.android.conscrypt/cacerts/* "\$tmp_copy"/

if ! mountpoint -q "\$system_ca_dir"; then
  mount -t tmpfs tmpfs "\$system_ca_dir"
fi

cp "\$tmp_copy"/* "\$system_ca_dir"/
cp "\$device_cert" "\$system_ca_dir/${MITM_CA_HASH}"
chown root:root "\$system_ca_dir"/*
chmod 644 "\$system_ca_dir"/*
chcon u:object_r:system_security_cacerts_file:s0 "\$system_ca_dir"/*
mount --bind "\$system_ca_dir" "\$conscrypt_ca_dir"

zygotes="\$(pidof zygote64 zygote webview_zygote com.android.chrome_zygote 2>/dev/null || true)"
for pid in \$zygotes; do
  nsenter --mount=/proc/\$pid/ns/mnt -- mount --bind "\$system_ca_dir" "\$conscrypt_ca_dir"
done

app_pids="\$(for z in \$zygotes; do ps -A -o PID,PPID | awk -v z="\$z" '\$2==z{print \$1}'; done | sort -u)"
for pid in \$app_pids; do
  nsenter --mount=/proc/\$pid/ns/mnt -- mount --bind "\$system_ca_dir" "\$conscrypt_ca_dir" || true
done
EOF

	log_success "mitmproxy system CA synced from ${MITM_CA_SOURCE}"
}

start_mitm_tmux() {
	need_cmd mitmdump
	mitm_ensure_ca_cert || return 1
	kill_mitm_listeners
	ensure_re_tmux

	if mitm_running; then
		log_success "mitmproxy listener already present on ${MITM_PORT}"
		return 0
	fi

	tmux send-keys -t "${TMUX_SESSION}:${TMUX_MITM_WINDOW}" C-c
	tmux send-keys -t "${TMUX_SESSION}:${TMUX_MITM_WINDOW}" "clear"
	tmux send-keys -t "${TMUX_SESSION}:${TMUX_MITM_WINDOW}" Enter
	tmux send-keys -t "${TMUX_SESSION}:${TMUX_MITM_WINDOW}" "$(mitm_command)"
	tmux send-keys -t "${TMUX_SESSION}:${TMUX_MITM_WINDOW}" Enter

	for _ in $(seq 1 15); do
		if mitm_running; then
			log_success "mitmproxy listening on ${MITM_HOST}:${MITM_PORT}"
			return 0
		fi
		sleep 1
	done

	error_exit "mitmproxy did not start on port ${MITM_PORT}"
}

proxy_set() {
	local proxy="$1"
	local block_quic="${2:-0}"
	adb_run shell settings put global http_proxy "${proxy}"
	log_success "http proxy set to ${proxy}"
	if [[ "${block_quic}" == "1" ]]; then
		adb_run shell "su 0 sh -c 'iptables -C OUTPUT -p udp --dport 443 -j REJECT 2>/dev/null || iptables -A OUTPUT -p udp --dport 443 -j REJECT; ip6tables -C OUTPUT -p udp --dport 443 -j REJECT 2>/dev/null || ip6tables -A OUTPUT -p udp --dport 443 -j REJECT'"
		log_success "QUIC blocking rules applied"
	fi
}

proxy_clear() {
	adb_run shell settings put global http_proxy :0
	adb_run shell "su 0 sh -c 'iptables -D OUTPUT -p udp --dport 443 -j REJECT 2>/dev/null || true; ip6tables -D OUTPUT -p udp --dport 443 -j REJECT 2>/dev/null || true'"
	log_success "proxy cleared and QUIC block rules removed"
}
