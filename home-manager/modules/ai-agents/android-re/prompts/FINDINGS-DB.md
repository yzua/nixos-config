# Findings Database

## Purpose

The findings database provides structured SQLite-based tracking for all discoveries during an Android RE assessment. Unlike flat markdown files, the database is queryable, supports cross-session continuity, and enables complex queries across hosts, services, vulnerabilities, credentials, and exploit chains.

Use the findings database alongside workspace markdown files (FINDINGS.md, NOTES.md) for a complete picture: the database for structured queries and relationships, markdown for narrative context and evidence descriptions.

## Location

```
~/Documents/<target>/findings.db
```

Initialized during workspace setup. Persists across sessions. Back up before destructive operations.

## Schema

### hosts

```sql
CREATE TABLE hosts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT,
    hostname TEXT,
    os TEXT,
    notes TEXT,
    first_seen TEXT,
    last_seen TEXT
);
```

Tracks discovered hosts. For Android RE, this includes the emulator, any backend servers discovered through traffic analysis, and companion devices.

| Column       | Type | Description                                                           |
| ------------ | ---- | --------------------------------------------------------------------- |
| `ip`         | TEXT | IP address (e.g., `10.0.2.15` for emulator, backend IPs from traffic) |
| `hostname`   | TEXT | Hostname or identifier                                                |
| `os`         | TEXT | Operating system (e.g., `Android 14 (API 34)`, `Ubuntu 22.04`)        |
| `notes`      | TEXT | Free-form context about the host                                      |
| `first_seen` | TEXT | ISO 8601 timestamp of first discovery                                 |
| `last_seen`  | TEXT | ISO 8601 timestamp of last update                                     |

### services

```sql
CREATE TABLE services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id INTEGER REFERENCES hosts(id),
    port INTEGER,
    protocol TEXT,
    service TEXT,
    version TEXT,
    banner TEXT,
    first_seen TEXT
);
```

Tracks services discovered on hosts. Primarily backend API servers found through traffic interception.

| Column       | Type    | Description                                           |
| ------------ | ------- | ----------------------------------------------------- |
| `host_id`    | INTEGER | Foreign key to hosts table                            |
| `port`       | INTEGER | Port number (e.g., `443`, `8080`)                     |
| `protocol`   | TEXT    | Protocol (e.g., `https`, `http`, `grpc`, `wss`)       |
| `service`    | TEXT    | Service name (e.g., `nginx`, `express`, `cloudflare`) |
| `version`    | TEXT    | Version string if identifiable                        |
| `banner`     | TEXT    | Server banner or header response                      |
| `first_seen` | TEXT    | ISO 8601 timestamp                                    |

### vulns

```sql
CREATE TABLE vulns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id INTEGER REFERENCES hosts(id),
    service_id INTEGER REFERENCES services(id),
    finding_id TEXT UNIQUE,
    title TEXT,
    severity TEXT CHECK(severity IN ('Critical','High','Medium','Low','Info')),
    owasp TEXT,
    status TEXT CHECK(status IN ('open','in_progress','confirmed','exploited','false_positive','remediated')),
    description TEXT,
    evidence_path TEXT,
    repro_steps TEXT,
    remediation TEXT,
    detection_yara TEXT,
    detection_sigma TEXT,
    detection_network TEXT,
    detection_siem TEXT,
    confidence REAL,
    created TEXT,
    updated TEXT
);
```

The primary findings table. Every vulnerability or security issue discovered during the assessment.

| Column              | Type        | Description                                                                |
| ------------------- | ----------- | -------------------------------------------------------------------------- |
| `host_id`           | INTEGER     | Host where the vulnerability exists                                        |
| `service_id`        | INTEGER     | Service/component where the vulnerability exists                           |
| `finding_id`        | TEXT UNIQUE | Unique identifier (e.g., `FIND-001`) matching EXPLOITATION-QUEUE.md        |
| `title`             | TEXT        | Short descriptive title                                                    |
| `severity`          | TEXT        | One of: Critical, High, Medium, Low, Info (see FINDINGS-PRIORITIZATION.md) |
| `owasp`             | TEXT        | OWASP Mobile Top 10 category (e.g., `M1`, `M2`, `M5`, `M8`)                |
| `status`            | TEXT        | Current status in the vulnerability lifecycle                              |
| `description`       | TEXT        | Detailed vulnerability description                                         |
| `evidence_path`     | TEXT        | Path to evidence files (screenshots, captures, scripts)                    |
| `repro_steps`       | TEXT        | Step-by-step reproduction instructions                                     |
| `remediation`       | TEXT        | Recommended fix                                                            |
| `detection_yara`    | TEXT        | YARA rule from DETECTION-PAIRING.md                                        |
| `detection_sigma`   | TEXT        | Sigma rule from DETECTION-PAIRING.md                                       |
| `detection_network` | TEXT        | Network IOC JSON from DETECTION-PAIRING.md                                 |
| `detection_siem`    | TEXT        | SIEM query from DETECTION-PAIRING.md                                       |
| `confidence`        | REAL        | 0.0-1.0 per SESSION-MEMORY.md confidence scoring                           |
| `created`           | TEXT        | ISO 8601 creation timestamp                                                |
| `updated`           | TEXT        | ISO 8601 last update timestamp                                             |

### credentials

```sql
CREATE TABLE credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id INTEGER REFERENCES hosts(id),
    service_id INTEGER REFERENCES services(id),
    username TEXT,
    hash_type TEXT,
    hash_value TEXT,
    cleartext TEXT,
    source TEXT,
    first_seen TEXT
);
```

Tracks discovered credentials: hardcoded API keys, extracted tokens, found passwords.

| Column       | Type    | Description                                                                              |
| ------------ | ------- | ---------------------------------------------------------------------------------------- |
| `host_id`    | INTEGER | Host where the credential was found                                                      |
| `service_id` | INTEGER | Service the credential applies to                                                        |
| `username`   | TEXT    | Username if applicable                                                                   |
| `hash_type`  | TEXT    | Hash algorithm (e.g., `bcrypt`, `md5`, `sha256`, `none`)                                 |
| `hash_value` | TEXT    | Hashed value                                                                             |
| `cleartext`  | TEXT    | Cleartext value if cracked or found in plaintext                                         |
| `source`     | TEXT    | Where the credential was found (e.g., `SharedPreferences`, `strings.xml`, `SQLite dump`) |
| `first_seen` | TEXT    | ISO 8601 timestamp                                                                       |

### chains

```sql
CREATE TABLE chains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    steps_json TEXT,
    score_reach REAL,
    score_reliability REAL,
    score_stealth REAL,
    score_speed REAL,
    score_impact REAL,
    total_score REAL,
    severity TEXT,
    status TEXT,
    created TEXT
);
```

Tracks exploit chains combining multiple findings. Scores follow FINDINGS-PRIORITIZATION.md chain scoring.

| Column              | Type | Description                                                        |
| ------------------- | ---- | ------------------------------------------------------------------ |
| `name`              | TEXT | Chain name (e.g., "SQLi + Root Bypass to Full Data Extraction")    |
| `description`       | TEXT | What the chain achieves                                            |
| `steps_json`        | TEXT | JSON array of finding_ids in order                                 |
| `score_reach`       | REAL | Reach score 1-5 (30% weight)                                       |
| `score_reliability` | REAL | Reliability score 1-5 (25% weight)                                 |
| `score_stealth`     | REAL | Stealth score 1-5 (20% weight)                                     |
| `score_speed`       | REAL | Speed score 1-5 (15% weight)                                       |
| `score_impact`      | REAL | Impact score 1-5 (10% weight)                                      |
| `total_score`       | REAL | Weighted total (4.0+ = Critical, 3.0-3.9 = High, 2.0-2.9 = Medium) |
| `severity`          | TEXT | Derived severity from total_score                                  |
| `status`            | TEXT | Chain status (open, confirmed, blocked, false_positive)            |
| `created`           | TEXT | ISO 8601 timestamp                                                 |

### session_log

```sql
CREATE TABLE session_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TEXT,
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
```

Session history mirroring SESSION-MEMORY.md session_history. Enables cross-session query of what was tried and what worked.

| Column                      | Type    | Description                              |
| --------------------------- | ------- | ---------------------------------------- |
| `session_date`              | TEXT    | ISO 8601 date of the session             |
| `goals_json`                | TEXT    | JSON array of session goals              |
| `findings_json`             | TEXT    | JSON array of findings made this session |
| `strategies_tried_json`     | TEXT    | JSON array of strategies attempted       |
| `strategies_succeeded_json` | TEXT    | JSON array of strategies that worked     |
| `strategies_failed_json`    | TEXT    | JSON array of strategies that failed     |
| `blocked_json`              | TEXT    | JSON array of blocked items              |
| `next_steps_json`           | TEXT    | JSON array of recommended next steps     |
| `duration_minutes`          | INTEGER | Session duration                         |
| `knowledge_added`           | INTEGER | New memory.json entries added            |
| `knowledge_updated`         | INTEGER | Existing memory.json entries updated     |

## Common Queries

### Open vulnerabilities by severity

```sql
SELECT finding_id, title, severity, owasp, confidence
FROM vulns
WHERE status IN ('open', 'in_progress', 'confirmed')
ORDER BY
    CASE severity
        WHEN 'Critical' THEN 1
        WHEN 'High' THEN 2
        WHEN 'Medium' THEN 3
        WHEN 'Low' THEN 4
        WHEN 'Info' THEN 5
    END,
    confidence DESC;
```

### Exploited findings with evidence

```sql
SELECT v.finding_id, v.title, v.severity, v.evidence_path, v.repro_steps
FROM vulns v
WHERE v.status = 'exploited'
ORDER BY v.confidence DESC;
```

### Findings without detection content

```sql
SELECT finding_id, title, severity
FROM vulns
WHERE status IN ('confirmed', 'exploited')
    AND (detection_yara IS NULL OR detection_yara = '')
    AND (detection_sigma IS NULL OR detection_sigma = '');
```

### Exploit chains scored 4.0+

```sql
SELECT name, description, total_score, severity, status
FROM chains
WHERE total_score >= 4.0
ORDER BY total_score DESC;
```

### Credentials by host

```sql
SELECT h.hostname, h.ip, c.username, c.hash_type, c.source, c.first_seen
FROM credentials c
JOIN hosts h ON c.host_id = h.id
ORDER BY h.hostname, c.first_seen;
```

### Cleartext credentials

```sql
SELECT c.username, c.cleartext, c.source, h.hostname
FROM credentials c
JOIN hosts h ON c.host_id = h.id
WHERE c.cleartext IS NOT NULL AND c.cleartext != '';
```

### Session history with findings count

```sql
SELECT s.session_date,
       s.duration_minutes,
       json_array_length(s.findings_json) AS findings_count,
       json_array_length(s.strategies_succeeded_json) AS successes,
       json_array_length(s.strategies_failed_json) AS failures,
       s.knowledge_added,
       s.next_steps_json
FROM session_log s
ORDER BY s.session_date DESC
LIMIT 10;
```

### Unconfirmed findings needing more testing

```sql
SELECT v.finding_id, v.title, v.severity, v.confidence, v.description
FROM vulns v
WHERE v.status IN ('open', 'in_progress')
    AND v.confidence < 0.7
ORDER BY v.confidence DESC;
```

### Findings by OWASP Mobile Top 10 category

```sql
SELECT owasp, COUNT(*) AS count,
       GROUP_CONCAT(finding_id || ': ' || title, ' | ') AS findings
FROM vulns
WHERE status != 'false_positive'
GROUP BY owasp
ORDER BY count DESC;
```

### All detection content for a finding

```sql
SELECT finding_id, title,
       CASE WHEN detection_yara IS NOT NULL AND detection_yara != '' THEN 'YES' ELSE 'NO' END AS has_yara,
       CASE WHEN detection_sigma IS NOT NULL AND detection_sigma != '' THEN 'YES' ELSE 'NO' END AS has_sigma,
       CASE WHEN detection_network IS NOT NULL AND detection_network != '' THEN 'YES' ELSE 'NO' END AS has_network,
       CASE WHEN detection_siem IS NOT NULL AND detection_siem != '' THEN 'YES' ELSE 'NO' END AS has_siem
FROM vulns
WHERE status IN ('confirmed', 'exploited');
```

### Chain details with finding titles

```sql
SELECT c.name, c.total_score, c.severity,
       GROUP_CONCAT(v.finding_id || ': ' || v.title, ' -> ') AS chain_steps
FROM chains c, json_each(c.steps_json) j
JOIN vulns v ON v.finding_id = j.value
GROUP BY c.id
ORDER BY c.total_score DESC;
```

### Recent findings from last N sessions

```sql
SELECT v.finding_id, v.title, v.severity, v.status, v.created
FROM vulns v
WHERE v.created >= date('now', '-7 days')
ORDER BY v.created DESC;
```

## CLI Helper

The `findings-android` command provides a wrapper around the SQLite database with structured subcommands. All commands operate on `~/Documents/<target>/findings.db`.

The wrapper currently uses positional arguments, not flag-style arguments. Use
raw `query` for fields the wrapper does not expose directly.

### Initialization

```bash
findings-android init ~/Documents/<target>
```

Creates a fresh `findings.db` at `~/Documents/<target>/findings.db` with all six tables. Safe to run on an existing database (no-op if tables exist).

### Adding Records

```bash
findings-android add-host ~/Documents/<target> <ip> <hostname> [os]
findings-android add-service ~/Documents/<target> <host_id> <port> <protocol> <service> [version]
findings-android add-vuln ~/Documents/<target> <FIND-NNN> "<title>" <Critical|High|Medium|Low|Info> <M1-M10> [status]
findings-android add-cred ~/Documents/<target> <host_id> <username> <hash_type> <hash_value> [source]
findings-android add-chain ~/Documents/<target> "<name>" "<description>" '<json_array_of_finding_ids>'
```

### Listing Records

```bash
findings-android list-hosts ~/Documents/<target>
findings-android list-vulns ~/Documents/<target> [--severity High] [--status open]
findings-android list-chains ~/Documents/<target>
```

### Updating Records

```bash
findings-android update-vuln ~/Documents/<target> <FIND-NNN> [--status exploited] [--confidence 0.9] [--evidence <path>]
```

### Session Logging

```bash
findings-android log-session ~/Documents/<target> '<goals_json>' '<findings_json>' '<next_steps_json>'
```

### Raw Queries

```bash
findings-android query ~/Documents/<target> "SELECT finding_id, title, severity FROM vulns WHERE status = 'exploited' ORDER BY confidence DESC"
findings-android query ~/Documents/<target> "SELECT * FROM chains WHERE total_score >= 4.0"
```

## Integration with Other Prompt Files

- **WORKFLOW.md**: Database initialization occurs in Phase 0 (Environment Validation). Findings are added during Phase 3 (Static Triage), Phase 3.7-3.9 (Semgrep/CodeQL analysis), and Phase 9 (Prove Findings). Session logging occurs in Phase 10 (Confidence Review).
- **SESSION-MEMORY.md**: The `session_log` table mirrors the `session_history` array in `memory.json`. Confidence scores in the `vulns` table should match knowledge entry confidence in memory. Use both for complete session tracking.
- **FINDINGS-PRIORITIZATION.md**: The `severity` and `owasp` columns use values from the adversarial priority order and OWASP Mobile Top 10 mapping. The `chains` table scores follow the five-dimension chain scoring model.
- **DETECTION-PAIRING.md**: The `detection_yara`, `detection_sigma`, `detection_network`, and `detection_siem` columns store detection content directly. Populate these during Phase 10 after detection content is written.
- **EXPLOITATION-QUEUE.md**: The `finding_id` column in the `vulns` table is the authoritative source for finding IDs. The exploitation queue references these IDs for cross-linking. Status values should be kept in sync between the queue and the database.
- **EXPLOIT-VERIFICATION.md**: The `status` column uses values that map to proof levels: `confirmed` requires Level 2+, `exploited` requires Level 3+, `false_positive` requires bypass exhaustion completion.
