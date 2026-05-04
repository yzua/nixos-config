# shellcheck shell=bash
# Shared SQLite findings database CLI implementation.
# Sourced by domain-specific adapters that define schema/projection variables.

DB_ARGS=() # Extra sqlite3 args (e.g. -cmd ".mode column")

# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/ai/_findings-schema.sh"

sqlite_cli() {
	if command -v sqlite3 >/dev/null 2>&1; then
		sqlite3 "${DB_ARGS[@]}" "$@"
	else
		python3 -c "
import sqlite3, sys
db = sys.argv[1]
sql = sys.argv[2]
conn = sqlite3.connect(db)
if sql.strip().upper().startswith('SELECT'):
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    if cols:
        print('\t'.join(cols))
        for row in cur:
            print('\t'.join(str(c) for c in row))
else:
    conn.execute(sql)
    conn.commit()
conn.close()
" "$@"
	fi
}

db_path() {
	local workspace="$1"
	local db="${workspace}/findings.db"
	printf '%s' "${db}"
}

cmd_init() {
	local workspace="$1"
	local db
	db="$(db_path "${workspace}")"

	if [[ -f "${db}" ]]; then
		log_info "database already exists: ${db}"
		return 0
	fi

	mkdir -p "${workspace}"
	sqlite_cli "${db}" "$(findings_schema_sql "${FINDINGS_SCHEMA_KIND}")"
	log_success "created findings database: ${db}"
}

cmd_add_host() {
	local workspace="$1"
	local ip="$2"
	local hostname="$3"
	local os="${4:-}"
	local db
	db="$(db_path "${workspace}")"
	[[ -f "${db}" ]] || error_exit "database not found: ${db}"

	local rowid
	rowid="$(sqlite_cli "${db}" \
		"INSERT INTO hosts (ip, hostname, os) VALUES ('${ip}', '${hostname}', '${os}');
         SELECT last_insert_rowid();")"
	log_success "host added: id=${rowid} ip=${ip}"
}

cmd_add_service() {
	local workspace="$1"
	local host_id="$2"
	local port="$3"
	local protocol="$4"
	local service="$5"
	local version="${6:-}"
	local db
	db="$(db_path "${workspace}")"
	[[ -f "${db}" ]] || error_exit "database not found: ${db}"

	local rowid
	rowid="$(sqlite_cli "${db}" \
		"INSERT INTO services (host_id, port, protocol, service, version)
         VALUES (${host_id}, ${port}, '${protocol}', '${service}', '${version}');
         SELECT last_insert_rowid();")"
	log_success "service added: id=${rowid} port=${port}/${protocol}"
}

cmd_add_vuln() {
	local workspace="$1"
	local finding_id="$2"
	local title="$3"
	local severity="$4"
	local owasp="${5:-}"
	local status="${6:-open}"
	local db
	db="$(db_path "${workspace}")"
	[[ -f "${db}" ]] || error_exit "database not found: ${db}"

	sqlite_cli "${db}" \
		"INSERT INTO vulns (finding_id, title, severity, owasp, status)
         VALUES ('${finding_id}', '${title}', '${severity}', '${owasp}', '${status}');"
	log_success "vuln added: ${finding_id} [${severity}]"
}

cmd_add_cred() {
	local workspace="$1"
	local host_id="$2"
	local username="$3"
	local hash_type="$4"
	local hash_value="$5"
	local source="${6:-}"
	local db
	db="$(db_path "${workspace}")"
	[[ -f "${db}" ]] || error_exit "database not found: ${db}"

	sqlite_cli "${db}" \
		"INSERT INTO credentials (host_id, username, hash_type, hash_value, source)
         VALUES (${host_id}, '${username}', '${hash_type}', '${hash_value}', '${source}');"
	log_success "credential added: ${username}@host${host_id}"
}

cmd_add_chain() {
	local workspace="$1"
	local name="$2"
	local description="$3"
	local steps_json="$4"
	local db
	db="$(db_path "${workspace}")"
	[[ -f "${db}" ]] || error_exit "database not found: ${db}"

	sqlite_cli "${db}" \
		"INSERT INTO chains (name, description, steps_json)
         VALUES ('${name}', '${description}', '${steps_json}');"
	log_success "chain added: ${name}"
}

cmd_log_session() {
	local workspace="$1"
	local goals_json="$2"
	local findings_json="$3"
	local next_steps_json="$4"
	local db
	db="$(db_path "${workspace}")"
	[[ -f "${db}" ]] || error_exit "database not found: ${db}"

	local session_date
	session_date="$(date -Iseconds)"
	sqlite_cli "${db}" \
		"INSERT INTO session_log (session_date, goals_json, findings_json, next_steps_json)
         VALUES ('${session_date}', '${goals_json}', '${findings_json}', '${next_steps_json}');"
	log_success "session logged: ${session_date}"
}

cmd_list_vulns() {
	local workspace="$1"
	shift
	local db
	db="$(db_path "${workspace}")"
	[[ -f "${db}" ]] || error_exit "database not found: ${db}"

	local sql="SELECT ${FINDINGS_LIST_VULNS_COLUMNS} FROM vulns WHERE 1=1"

	while [[ $# -gt 0 ]]; do
		case "$1" in
		--severity)
			sql="${sql} AND severity = '$2'"
			shift 2
			;;
		--status)
			sql="${sql} AND status = '$2'"
			shift 2
			;;
		*)
			shift
			;;
		esac
	done

	sql="${sql} ORDER BY CASE severity
        WHEN 'Critical' THEN 1
        WHEN 'High' THEN 2
        WHEN 'Medium' THEN 3
        WHEN 'Low' THEN 4
        WHEN 'Info' THEN 5
        END, finding_id;"

	DB_ARGS=(-cmd ".mode column" -cmd ".headers on")
	sqlite_cli "${db}" "${sql}"
}

cmd_list_hosts() {
	local workspace="$1"
	local db
	db="$(db_path "${workspace}")"
	[[ -f "${db}" ]] || error_exit "database not found: ${db}"

	DB_ARGS=(-cmd ".mode column" -cmd ".headers on")
	sqlite_cli "${db}" "SELECT id, ip, hostname, os, first_seen, last_seen FROM hosts ORDER BY id;"
}

cmd_list_chains() {
	local workspace="$1"
	local db
	db="$(db_path "${workspace}")"
	[[ -f "${db}" ]] || error_exit "database not found: ${db}"

	DB_ARGS=(-cmd ".mode column" -cmd ".headers on")
	sqlite_cli "${db}" \
		"SELECT id, name, total_score, severity, status, created FROM chains ORDER BY total_score DESC;"
}

cmd_update_vuln() {
	local workspace="$1"
	local finding_id="$2"
	shift 2
	local db
	db="$(db_path "${workspace}")"
	[[ -f "${db}" ]] || error_exit "database not found: ${db}"

	local sets=()
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--status)
			sets+=("status = '${2}'")
			shift 2
			;;
		--evidence)
			sets+=("evidence_path = '${2}'")
			shift 2
			;;
		--confidence)
			sets+=("confidence = ${2}")
			shift 2
			;;
		*)
			shift
			;;
		esac
	done

	if [[ ${#sets[@]} -eq 0 ]]; then
		log_warning "no fields to update"
		return 0
	fi

	local set_clause
	set_clause="$(printf '%s, ' "${sets[@]}")"
	set_clause="${set_clause%, }"

	sqlite_cli "${db}" \
		"UPDATE vulns SET ${set_clause}, updated = datetime('now') WHERE finding_id = '${finding_id}';"
	log_success "vuln updated: ${finding_id}"
}

cmd_query() {
	local workspace="$1"
	local sql="$2"
	local db
	db="$(db_path "${workspace}")"
	[[ -f "${db}" ]] || error_exit "database not found: ${db}"

	local upper_sql
	upper_sql="$(echo "${sql}" | sed 's/^\s*//' | tr '[:lower:]' '[:upper:]')"
	if [[ "${upper_sql}" != SELECT* ]]; then
		error_exit "only SELECT queries are allowed"
	fi

	DB_ARGS=(-cmd ".mode column" -cmd ".headers on")
	sqlite_cli "${db}" "${sql}"
}

usage() {
	cat <<EOF
Usage: ${FINDINGS_USAGE_NAME} <command> <workspace> [args...]

Commands:
  init <workspace>                                      Create findings.db with full schema
  add-host <workspace> <ip> <hostname> [os]             Insert host, print new ID
  add-service <workspace> <host_id> <port> <protocol> <service> [version]
                                                        Insert service
  add-vuln <workspace> <finding_id> <title> <severity> <owasp> [status]
                                                        Insert vulnerability
  add-cred <workspace> <host_id> <username> <hash_type> <hash_value> [source]
                                                        Insert credential
  add-chain <workspace> <name> <description> <steps_json>
                                                        Insert attack chain
  log-session <workspace> <goals_json> <findings_json> <next_steps_json>
                                                        Insert session log entry
  list-vulns <workspace> [--severity LEVEL] [--status STATUS]
                                                        Query vulns with optional filters
  list-hosts <workspace>                                List all hosts
  list-chains <workspace>                               List all chains with scores
  update-vuln <workspace> <finding_id> --status <status> [--evidence <path>] [--confidence <n>]
                                                        Update vuln fields
  query <workspace> <sql>                               Raw SQL query (SELECT only)
EOF
}

findings_main() {
	local cmd="${1:-}"
	case "${cmd}" in
	init)
		[[ -n "${2:-}" ]] || error_exit "init requires workspace path"
		cmd_init "$2"
		;;
	add-host)
		[[ -n "${2:-}" ]] || error_exit "add-host requires workspace"
		[[ -n "${3:-}" ]] || error_exit "add-host requires ip"
		[[ -n "${4:-}" ]] || error_exit "add-host requires hostname"
		cmd_add_host "$2" "$3" "$4" "${5:-}"
		;;
	add-service)
		[[ -n "${2:-}" ]] || error_exit "add-service requires workspace"
		[[ -n "${3:-}" ]] || error_exit "add-service requires host_id"
		[[ -n "${4:-}" ]] || error_exit "add-service requires port"
		[[ -n "${5:-}" ]] || error_exit "add-service requires protocol"
		[[ -n "${6:-}" ]] || error_exit "add-service requires service"
		cmd_add_service "$2" "$3" "$4" "$5" "$6" "${7:-}"
		;;
	add-vuln)
		[[ -n "${2:-}" ]] || error_exit "add-vuln requires workspace"
		[[ -n "${3:-}" ]] || error_exit "add-vuln requires finding_id"
		[[ -n "${4:-}" ]] || error_exit "add-vuln requires title"
		[[ -n "${5:-}" ]] || error_exit "add-vuln requires severity"
		cmd_add_vuln "$2" "$3" "$4" "$5" "${6:-}" "${7:-}"
		;;
	add-cred)
		[[ -n "${2:-}" ]] || error_exit "add-cred requires workspace"
		[[ -n "${3:-}" ]] || error_exit "add-cred requires host_id"
		[[ -n "${4:-}" ]] || error_exit "add-cred requires username"
		[[ -n "${5:-}" ]] || error_exit "add-cred requires hash_type"
		[[ -n "${6:-}" ]] || error_exit "add-cred requires hash_value"
		cmd_add_cred "$2" "$3" "$4" "$5" "$6" "${7:-}"
		;;
	add-chain)
		[[ -n "${2:-}" ]] || error_exit "add-chain requires workspace"
		[[ -n "${3:-}" ]] || error_exit "add-chain requires name"
		[[ -n "${4:-}" ]] || error_exit "add-chain requires description"
		[[ -n "${5:-}" ]] || error_exit "add-chain requires steps_json"
		cmd_add_chain "$2" "$3" "$4" "$5"
		;;
	log-session)
		[[ -n "${2:-}" ]] || error_exit "log-session requires workspace"
		[[ -n "${3:-}" ]] || error_exit "log-session requires goals_json"
		[[ -n "${4:-}" ]] || error_exit "log-session requires findings_json"
		[[ -n "${5:-}" ]] || error_exit "log-session requires next_steps_json"
		cmd_log_session "$2" "$3" "$4" "$5"
		;;
	list-vulns)
		[[ -n "${2:-}" ]] || error_exit "list-vulns requires workspace"
		cmd_list_vulns "$2" "${@:3}"
		;;
	list-hosts)
		[[ -n "${2:-}" ]] || error_exit "list-hosts requires workspace"
		cmd_list_hosts "$2"
		;;
	list-chains)
		[[ -n "${2:-}" ]] || error_exit "list-chains requires workspace"
		cmd_list_chains "$2"
		;;
	update-vuln)
		[[ -n "${2:-}" ]] || error_exit "update-vuln requires workspace"
		[[ -n "${3:-}" ]] || error_exit "update-vuln requires finding_id"
		cmd_update_vuln "$2" "$3" "${@:4}"
		;;
	query)
		[[ -n "${2:-}" ]] || error_exit "query requires workspace"
		[[ -n "${3:-}" ]] || error_exit "query requires SQL"
		cmd_query "$2" "$3"
		;;
	*)
		usage
		exit 1
		;;
	esac
}
