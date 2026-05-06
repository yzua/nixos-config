#!/usr/bin/env bash
# Focused tests for report helper and collector behavior.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/../../lib/test-helpers.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/report-helpers.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/report-collectors.sh"

assert_true "json_is_empty handles empty string" json_is_empty ""
assert_true "json_is_empty handles null" json_is_empty "null"
assert_true "json_is_empty handles []" json_is_empty "[]"
assert_true "json_is_empty handles {}" json_is_empty "{}"
assert_false "json_is_empty rejects non-empty object" json_is_empty '{"value":1}'

epoch_24h="$(epoch_hours_ago 24)"
assert_regex "$epoch_24h" '^[0-9]+$' "epoch_hours_ago returns numeric epoch"
iso_7d="$(iso_days_ago 7)"
assert_contains "$iso_7d" "T" "iso_days_ago returns ISO timestamp"

table_header_output="$(print_table_header "| A | B |" "|---|---|")"
assert_contains "$table_header_output" "| A | B |" "print_table_header emits columns line"
assert_contains "$table_header_output" "|---|---|" "print_table_header emits separator line"

feature_gate_msg="$(require_enabled_feature "false" "Netdata" || true)"
assert_contains "$feature_gate_msg" "[unavailable] Netdata not enabled." "require_enabled_feature emits unavailable message"

# shellcheck disable=SC2329 # Invoked indirectly by sourced collector functions.
safe_cmd() {
	if [[ "$1" == "systemctl" && "$2" == "list-timers" ]]; then
		cat <<'EOF'
Mon 2026-02-16 09:00:00 UTC 1h left Mon 2026-02-16 08:00:00 UTC 2h ago apt-daily.timer apt-daily.service
Tue 2026-02-17 01:00:00 UTC 5h left Mon 2026-02-16 20:00:00 UTC 6h ago fstrim.timer fstrim.service
EOF
		return 0
	fi
	return 1
}

tmp_logs_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_logs_dir"' EXIT

printf 'fatal: boom\n' >"${tmp_logs_dir}/error.log"
printf 'all good\n' >"${tmp_logs_dir}/ok.log"

assert_eq "$(scan_error_log_count "" "$tmp_logs_dir")" "1" "scan_error_log_count counts only matching log files"
assert_eq "$(scan_error_log_count "0" "$tmp_logs_dir")" "1" "scan_error_log_count honors mtime filters"

timers_output="$(collect_systemd_timers)"
assert_contains "$timers_output" "| apt-daily.timer | Mon 2026-02-16 09:00:00 |" "timers table uses timer unit name"
assert_contains "$timers_output" "| fstrim.timer | Tue 2026-02-17 01:00:00 |" "timers table includes second timer"
assert_not_contains "$timers_output" "| apt-daily.service |" "timers table does not use activates service as timer name"

# shellcheck disable=SC2329 # Invoked indirectly by sourced collector functions.
safe_cmd() {
	if [[ "$1" == "systemctl" && "$2" == "--no-legend" ]]; then
		cat <<'EOF'
alpha.service loaded failed failed Alpha service
beta.socket loaded failed failed Beta socket
EOF
		return 0
	fi
	return 1
}

failed_services_output="$(collect_systemd_errors 24)"
assert_contains "$failed_services_output" "- \`alpha.service\`" "systemd errors lists failed unit names"
assert_contains "$failed_services_output" "- \`beta.socket\`" "systemd errors lists multiple failed units"

# shellcheck disable=SC2034 # Used by sourced collector functions.
HAS_FAIL2BAN="false"
# shellcheck disable=SC2034
HAS_OPENSNITCH="false"
# shellcheck disable=SC2034
HAS_SECURE_BOOT="false"
security_output="$(collect_security)"
assert_contains "$security_output" "- fail2ban: [unavailable]" "security collector reports fail2ban unavailable"
assert_contains "$security_output" "- OpenSnitch: [unavailable]" "security collector reports OpenSnitch unavailable"
assert_contains "$security_output" "- Secure Boot: [unavailable]" "security collector reports Secure Boot unavailable"

# shellcheck disable=SC2034
HAS_LOKI="false"
loki_output="$(collect_loki_errors)"
assert_contains "$loki_output" "[unavailable] Loki not enabled." "loki collector reports disabled service"

echo "All system report helper/collector tests passed."
