# Findings Database

## Purpose

The findings database provides structured SQLite-based tracking for all discoveries during a web security assessment. Unlike flat markdown files, the database is queryable, supports cross-session continuity, and enables complex queries across hosts, services, endpoints, vulnerabilities, credentials, and exploit chains.

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

Tracks discovered hosts: the primary target, subdomains, backend servers, and cloud infrastructure.

| Column       | Type | Description                                                                  |
| ------------ | ---- | ---------------------------------------------------------------------------- |
| `ip`         | TEXT | IP address (e.g., `203.0.113.50`, resolves from DNS)                         |
| `hostname`   | TEXT | Hostname or FQDN (e.g., `api.example.target.com`)                            |
| `os`         | TEXT | Operating system if identifiable (e.g., `Ubuntu 22.04`, `Amazon Linux 2023`) |
| `notes`      | TEXT | Free-form context about the host (CDN, WAF, cloud provider)                  |
| `first_seen` | TEXT | ISO 8601 timestamp of first discovery                                        |
| `last_seen`  | TEXT | ISO 8601 timestamp of last update                                            |

### services

```sql
CREATE TABLE services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id INTEGER REFERENCES hosts(id),
    url TEXT,
    port INTEGER,
    protocol TEXT,
    service TEXT,
    version TEXT,
    banner TEXT,
    first_seen TEXT
);
```

Tracks services and endpoints discovered during reconnaissance. The `url` field captures the full URL path, making this table endpoint-aware.

| Column       | Type    | Description                                                          |
| ------------ | ------- | -------------------------------------------------------------------- |
| `host_id`    | INTEGER | Foreign key to hosts table                                           |
| `url`        | TEXT    | Full URL (e.g., `https://api.example.target.com/v1/users`)           |
| `port`       | INTEGER | Port number (e.g., `443`, `8080`, `3000`)                            |
| `protocol`   | TEXT    | Protocol (e.g., `https`, `http`, `wss`, `grpc`)                      |
| `service`    | TEXT    | Service/framework name (e.g., `nginx`, `express`, `rails`, `apache`) |
| `version`    | TEXT    | Version string if identifiable                                       |
| `banner`     | TEXT    | Server banner or header response                                     |
| `first_seen` | TEXT    | ISO 8601 timestamp                                                   |

### vulns

```sql
CREATE TABLE vulns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id INTEGER REFERENCES hosts(id),
    service_id INTEGER REFERENCES services(id),
    endpoint TEXT,
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

The primary findings table. Every vulnerability or security issue discovered during the assessment. The `endpoint` field provides direct URL-level tracking.

| Column              | Type        | Description                                                                |
| ------------------- | ----------- | -------------------------------------------------------------------------- |
| `host_id`           | INTEGER     | Host where the vulnerability exists                                        |
| `service_id`        | INTEGER     | Service where the vulnerability exists                                     |
| `endpoint`          | TEXT        | Specific endpoint URL or path (e.g., `/api/v1/users/profiles`)             |
| `finding_id`        | TEXT UNIQUE | Unique identifier (e.g., `FIND-001`) matching EXPLOITATION-QUEUE.md        |
| `title`             | TEXT        | Short descriptive title                                                    |
| `severity`          | TEXT        | One of: Critical, High, Medium, Low, Info (see FINDINGS-PRIORITIZATION.md) |
| `owasp`             | TEXT        | OWASP Top 10 2021 category (e.g., `A01`, `A03`, `A05`, `A07`)              |
| `status`            | TEXT        | Current status in the vulnerability lifecycle                              |
| `description`       | TEXT        | Detailed vulnerability description                                         |
| `evidence_path`     | TEXT        | Path to evidence files (screenshots, captures, scripts)                    |
| `repro_steps`       | TEXT        | Step-by-step reproduction with HTTP method + URL + headers + body          |
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

Tracks discovered credentials: hardcoded API keys, extracted passwords, JWT secrets, database connection strings.

| Column       | Type    | Description                                                                              |
| ------------ | ------- | ---------------------------------------------------------------------------------------- |
| `host_id`    | INTEGER | Host where the credential was found                                                      |
| `service_id` | INTEGER | Service the credential applies to                                                        |
| `username`   | TEXT    | Username if applicable                                                                   |
| `hash_type`  | TEXT    | Hash algorithm (e.g., `bcrypt`, `md5`, `sha256`, `jwt_secret`, `none`)                   |
| `hash_value` | TEXT    | Hashed value                                                                             |
| `cleartext`  | TEXT    | Cleartext value if cracked or found in plaintext                                         |
| `source`     | TEXT    | Where the credential was found (e.g., `JavaScript source`, `.env exposure`, `SQLi dump`) |
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

| Column              | Type | Description                                                         |
| ------------------- | ---- | ------------------------------------------------------------------- |
| `name`              | TEXT | Chain name (e.g., "SSRF + Cloud Metadata to Full Account Takeover") |
| `description`       | TEXT | What the chain achieves                                             |
| `steps_json`        | TEXT | JSON array of finding_ids in order                                  |
| `score_reach`       | REAL | Reach score 1-5 (30% weight)                                        |
| `score_reliability` | REAL | Reliability score 1-5 (25% weight)                                  |
| `score_stealth`     | REAL | Stealth score 1-5 (20% weight)                                      |
| `score_speed`       | REAL | Speed score 1-5 (15% weight)                                        |
| `score_impact`      | REAL | Impact score 1-5 (10% weight)                                       |
| `total_score`       | REAL | Weighted total (4.0+ = Critical, 3.0-3.9 = High, 2.0-2.9 = Medium)  |
| `severity`          | TEXT | Derived severity from total_score                                   |
| `status`            | TEXT | Chain status (open, confirmed, blocked, false_positive)             |
| `created`           | TEXT | ISO 8601 timestamp                                                  |

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
SELECT finding_id, title, severity, endpoint, owasp, confidence
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

### Vulnerabilities by endpoint

```sql
SELECT endpoint, COUNT(*) AS vuln_count,
       GROUP_CONCAT(finding_id || ': ' || title, ' | ') AS findings
FROM vulns
WHERE status != 'false_positive'
GROUP BY endpoint
ORDER BY vuln_count DESC;
```

### CORS-related findings

```sql
SELECT finding_id, title, endpoint, severity, description
FROM vulns
WHERE title LIKE '%CORS%' OR description LIKE '%cors%' OR description LIKE '%Access-Control%'
ORDER BY severity, confidence DESC;
```

### Authentication findings per URL

```sql
SELECT v.finding_id, v.title, v.endpoint, v.severity, v.status
FROM vulns v
WHERE v.owasp = 'A07'
    OR v.title LIKE '%auth%'
    OR v.title LIKE '%JWT%'
    OR v.title LIKE '%session%'
    OR v.title LIKE '%token%'
ORDER BY v.endpoint, v.severity;
```

### Exploited findings with evidence

```sql
SELECT v.finding_id, v.title, v.severity, v.endpoint, v.evidence_path, v.repro_steps
FROM vulns v
WHERE v.status = 'exploited'
ORDER BY v.confidence DESC;
```

### Findings without detection content

```sql
SELECT finding_id, title, severity, endpoint
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

### Credentials by host and service

```sql
SELECT h.hostname, s.url, c.username, c.hash_type, c.source, c.first_seen
FROM credentials c
JOIN hosts h ON c.host_id = h.id
LEFT JOIN services s ON c.service_id = s.id
ORDER BY h.hostname, c.first_seen;
```

### Cleartext credentials with source

```sql
SELECT c.username, c.cleartext, c.source, s.url
FROM credentials c
LEFT JOIN services s ON c.service_id = s.id
WHERE c.cleartext IS NOT NULL AND c.cleartext != '';
```

### Endpoints by HTTP method (from repro_steps)

```sql
SELECT endpoint,
       CASE
           WHEN repro_steps LIKE 'GET %' THEN 'GET'
           WHEN repro_steps LIKE 'POST %' THEN 'POST'
           WHEN repro_steps LIKE 'PUT %' THEN 'PUT'
           WHEN repro_steps LIKE 'DELETE %' THEN 'DELETE'
           WHEN repro_steps LIKE 'PATCH %' THEN 'PATCH'
           ELSE 'UNKNOWN'
       END AS http_method,
       finding_id, title, severity
FROM vulns
WHERE endpoint IS NOT NULL AND status != 'false_positive'
ORDER BY endpoint, http_method;
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
SELECT v.finding_id, v.title, v.severity, v.endpoint, v.confidence
FROM vulns v
WHERE v.status IN ('open', 'in_progress')
    AND v.confidence < 0.7
ORDER BY v.confidence DESC;
```

### Findings by OWASP Top 10 category

```sql
SELECT owasp, COUNT(*) AS count,
       GROUP_CONCAT(finding_id || ': ' || title, ' | ') AS findings
FROM vulns
WHERE status != 'false_positive'
GROUP BY owasp
ORDER BY count DESC;
```

### Chain details with finding titles and endpoints

```sql
SELECT c.name, c.total_score, c.severity,
       GROUP_CONCAT(v.finding_id || ' (' || v.endpoint || ')', ' -> ') AS chain_steps
FROM chains c, json_each(c.steps_json) j
JOIN vulns v ON v.finding_id = j.value
GROUP BY c.id
ORDER BY c.total_score DESC;
```

### All services with their vulnerability count

```sql
SELECT s.url, s.service, s.version, COUNT(v.id) AS vuln_count
FROM services s
LEFT JOIN vulns v ON v.service_id = s.id AND v.status != 'false_positive'
GROUP BY s.id
ORDER BY vuln_count DESC;
```

## CLI Helper

The `findings-web` command provides a wrapper around the SQLite database with structured subcommands. All commands operate on `~/Documents/<target>/findings.db`.

The wrapper currently uses positional arguments, not flag-style arguments. Use
raw `query` for fields the wrapper does not expose directly.

### Initialization

```bash
findings-web init ~/Documents/<target>
```

Creates a fresh `findings.db` at `~/Documents/<target>/findings.db` with all six tables. Safe to run on an existing database (no-op if tables exist).

### Adding Records

```bash
findings-web add-host ~/Documents/<target> <ip> <hostname> [os]
findings-web add-service ~/Documents/<target> <host_id> <port> <protocol> <service> [version]
findings-web add-vuln ~/Documents/<target> <FIND-NNN> "<title>" <Critical|High|Medium|Low|Info> <A01-A10> [status]
findings-web add-cred ~/Documents/<target> <host_id> <username> <hash_type> <hash_value> [source]
findings-web add-chain ~/Documents/<target> "<name>" "<description>" '<json_array_of_finding_ids>'
```

### Listing Records

```bash
findings-web list-hosts ~/Documents/<target>
findings-web list-vulns ~/Documents/<target> [--severity High] [--status open]
findings-web list-chains ~/Documents/<target>
```

### Updating Records

```bash
findings-web update-vuln ~/Documents/<target> <FIND-NNN> [--status exploited] [--confidence 0.9] [--evidence <path>]
```

### Session Logging

```bash
findings-web log-session ~/Documents/<target> '<goals_json>' '<findings_json>' '<next_steps_json>'
```

### Raw Queries

```bash
findings-web query ~/Documents/<target> "SELECT finding_id, title, endpoint, severity FROM vulns WHERE status = 'exploited' ORDER BY confidence DESC"
findings-web query ~/Documents/<target> "SELECT url, service, version FROM services ORDER BY url"
findings-web query ~/Documents/<target> "SELECT * FROM chains WHERE total_score >= 4.0"
```

## Integration with Other Prompt Files

- **WORKFLOW.md**: Database initialization occurs in Phase 0 (Environment Validation). Findings are added during Phase 4 (Content Discovery), Phase 5 (Automated Scanning), and Phase 6 (Vulnerability Testing). Session logging occurs in Phase 9 (Confidence Review).
- **SESSION-MEMORY.md**: The `session_log` table mirrors the `session_history` array in `memory.json`. Confidence scores in the `vulns` table should match knowledge entry confidence in memory. Use both for complete session tracking.
- **FINDINGS-PRIORITIZATION.md**: The `severity` and `owasp` columns use values from the adversarial priority order and OWASP Top 10 2021 mapping. The `chains` table scores follow the five-dimension chain scoring model.
- **DETECTION-PAIRING.md**: The `detection_yara`, `detection_sigma`, `detection_network`, and `detection_siem` columns store detection content directly. Populate these during Phase 9 after detection content is written.
- **EXPLOITATION-QUEUE.md**: The `finding_id` column in the `vulns` table is the authoritative source for finding IDs. The exploitation queue references these IDs for cross-linking. Status values should be kept in sync between the queue and the database.
- **EXPLOIT-VERIFICATION.md**: The `status` column uses values that map to proof levels: `confirmed` requires Level 2+, `exploited` requires Level 3+, `false_positive` requires bypass exhaustion completion.
