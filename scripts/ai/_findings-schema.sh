# shellcheck shell=bash
# Shared SQLite schema renderer for RE findings databases.

findings_schema_sql() {
	local schema_kind="$1"
	local service_extra_columns=""
	local vuln_extra_columns=""

	case "${schema_kind}" in
	android) ;;
	web)
		service_extra_columns=$'    url TEXT,\n'
		vuln_extra_columns=$'    endpoint TEXT,\n'
		;;
	*) error_exit "unknown findings schema: ${schema_kind}" ;;
	esac

	cat <<SQL
CREATE TABLE IF NOT EXISTS hosts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL,
    hostname TEXT,
    os TEXT,
    notes TEXT,
    first_seen TEXT DEFAULT (datetime('now')),
    last_seen TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id INTEGER REFERENCES hosts(id),
${service_extra_columns}    port INTEGER NOT NULL,
    protocol TEXT DEFAULT 'tcp',
    service TEXT,
    version TEXT,
    banner TEXT,
    first_seen TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS vulns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id INTEGER REFERENCES hosts(id),
    service_id INTEGER REFERENCES services(id),
    finding_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    severity TEXT CHECK(severity IN ('Critical','High','Medium','Low','Info')) NOT NULL,
    owasp TEXT,
    status TEXT CHECK(status IN ('open','in_progress','confirmed','exploited','false_positive','remediated')) DEFAULT 'open',
${vuln_extra_columns}    description TEXT,
    evidence_path TEXT,
    repro_steps TEXT,
    remediation TEXT,
    detection_yara TEXT,
    detection_sigma TEXT,
    detection_network TEXT,
    detection_siem TEXT,
    confidence REAL DEFAULT 0.0,
    created TEXT DEFAULT (datetime('now')),
    updated TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id INTEGER REFERENCES hosts(id),
    service_id INTEGER REFERENCES services(id),
    username TEXT,
    hash_type TEXT,
    hash_value TEXT,
    cleartext TEXT,
    source TEXT,
    first_seen TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS chains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    steps_json TEXT,
    score_reach REAL DEFAULT 0.0,
    score_reliability REAL DEFAULT 0.0,
    score_stealth REAL DEFAULT 0.0,
    score_speed REAL DEFAULT 0.0,
    score_impact REAL DEFAULT 0.0,
    total_score REAL DEFAULT 0.0,
    severity TEXT,
    status TEXT DEFAULT 'identified',
    created TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS session_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TEXT NOT NULL,
    goals_json TEXT,
    findings_json TEXT,
    strategies_tried_json TEXT,
    strategies_succeeded_json TEXT,
    strategies_failed_json TEXT,
    blocked_json TEXT,
    next_steps_json TEXT,
    duration_minutes INTEGER,
    knowledge_added INTEGER DEFAULT 0,
    knowledge_updated INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_vulns_severity ON vulns(severity);
CREATE INDEX IF NOT EXISTS idx_vulns_status ON vulns(status);
CREATE INDEX IF NOT EXISTS idx_vulns_finding_id ON vulns(finding_id);
SQL
}
