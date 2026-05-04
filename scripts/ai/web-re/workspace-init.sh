#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/lib/logging.sh"

trap 'log_error "command failed at line ${LINENO}: ${BASH_COMMAND}"' ERR

DOCS_ROOT="${DOCS_ROOT:-${HOME}/Documents}"

# shellcheck source=scripts/ai/web-re/_helpers.sh
source "${SCRIPT_DIR}/_helpers.sh"
# shellcheck source=scripts/ai/_workspace-init-common.sh
source "${REPO_ROOT}/scripts/ai/_workspace-init-common.sh"

usage() {
	cat <<'EOF'
Usage: workspace-init.sh <command> [args]

Commands:
  init TARGET_NAME [URL]   Create target workspace at ~/Documents/<name>
EOF
}

init_workspace() {
	local target_name="$1"
	local target_url="${2:-}"
	local workspace="${DOCS_ROOT}/${target_name}"

	log_info "initializing workspace at ${workspace}"
	mkdir -p "${workspace}"/{scripts,evidence/{screenshots,http-logs,pcaps},analysis}

	# README.md -- target overview
	write_template "${workspace}/README.md" <<TEMPLATE
# ${target_name}

## Target Metadata

| Field     | Value                                                          |
| --------- | -------------------------------------------------------------- |
| Target    | ${target_name}                                                 |
| URL       | ${target_url:-_to be filled_}                                  |
| Init date | $(date -I)                                                     |
| Scope     | Full assessment: recon + injection + auth + crypto + API + XSS |

## Session Log

See [SESSIONS.md](SESSIONS.md) for per-session history.

## Quick Links

- [Findings](FINDINGS.md)
- [Endpoints](ENDPOINTS.md)
- [Attack Surface Map](ATTACK-SURFACE.md)
- [Running Notes](NOTES.md)
TEMPLATE

	# FINDINGS.md -- OWASP Web Top 10 2021 classified
	write_template "${workspace}/FINDINGS.md" <<'TEMPLATE'
# Findings: {TARGET_NAME}

## Severity Definitions

| Severity | Criteria |
|----------|----------|
| Critical | Remote code execution, auth bypass, data breach with no user interaction |
| High     | Privilege escalation, sensitive data exposure, auth bypass requiring user interaction |
| Medium   | Limited data leak, DoS, info disclosure requiring specific conditions |
| Low      | Minor info leak, best practice violations, low-impact issues |
| Info     | Observations useful for context but not directly exploitable |

## A01:2021 Broken Access Control

<!-- IDOR, forced browsing, missing function-level access control, CORS misconfiguration -->

## A02:2021 Cryptographic Failures

<!-- Cleartext transmission, weak TLS, sensitive data in URLs, missing encryption at rest -->

## A03:2021 Injection

<!-- SQL injection, NoSQL injection, OS command injection, LDAP injection, XSS -->

## A04:2021 Insecure Design

<!-- Missing rate limiting, insecure default configurations, trust boundary violations -->

## A05:2021 Security Misconfiguration

<!-- Default credentials, unnecessary features enabled, verbose errors, missing security headers -->

## A06:2021 Vulnerable and Outdated Components

<!-- Known CVEs in frameworks/libraries, unmaintained dependencies -->

## A07:2021 Identification and Authentication Failures

<!-- Weak password policies, session fixation, credential stuffing, missing MFA -->

## A08:2021 Software and Data Integrity Failures

<!-- Insecure CI/CD, unsigned updates, deserialization flaws, unverified CDN -->

## A09:2021 Security Logging and Monitoring Failures

<!-- Missing audit logs, no alerting, attack detection gaps -->

## A10:2021 Server-Side Request Forgery

<!-- SSRF via URL parameters, internal service scanning, cloud metadata access -->

---

## Finding Template

```markdown
### FIND-NNN: {Title}

- **Severity**: Critical/High/Medium/Low/Info
- **OWASP**: A??:2021
- **Status**: Confirmed / Investigating / False Positive
- **Location**: URL/endpoint/parameter
- **Impact**: what attacker can achieve
- **Evidence**: screenshot path, HTTP request/response, tool output
- **Repro**: numbered steps
- **Remediation**: suggested fix
```
TEMPLATE

	# NOTES.md -- running notes
	write_template "${workspace}/NOTES.md" <<'TEMPLATE'
# Notes: {TARGET_NAME}

## Observations

<!-- General observations about the target, its architecture, and behavior -->

## Hypotheses

<!-- Unverified theories to investigate. Format: H1: description [status] -->

## Blocked Items

<!-- Things that are blocked and why. Include the specific blocker and potential bypass. -->

## Next Steps

<!-- Ordered list of what to investigate next session -->
TEMPLATE

	# ENDPOINTS.md -- discovered URLs/APIs
	write_template "${workspace}/ENDPOINTS.md" <<'TEMPLATE'
# Endpoints: {TARGET_NAME}

## Base URLs

<!-- Discovered base URLs: production, staging, API, CDN -->

## Authentication Endpoints

| Method | URL | Purpose | Auth Required | Notes |
|--------|-----|---------|---------------|-------|

## API Endpoints

| Method | URL | Purpose | Auth Required | Params | Notes |
|--------|-----|---------|---------------|--------|-------|

## Static Resources

<!-- JS bundles, CSS, images, fonts with interesting paths -->

## Third-Party Services

<!-- Analytics, CDN, payment processors, auth providers, API gateways -->
TEMPLATE

	# ATTACK-SURFACE.md
	write_template "${workspace}/ATTACK-SURFACE.md" <<'TEMPLATE'
# Attack Surface: {TARGET_NAME}

## Entry Points

<!-- URL parameters, form inputs, file uploads, API endpoints, WebSocket connections -->

## Network Surface

<!-- API endpoints, backend services, CDN, third-party integrations, WebSocket -->

## Authentication Surface

<!-- Login, registration, password reset, MFA, session management, OAuth flows -->

## Client-Side Surface

<!-- JavaScript bundles, localStorage, cookies, DOM-based sinks, postMessage handlers -->

## Trust Boundaries

<!-- Where does the application trust external input? Where are auth checks enforced? -->

## Risk Ranking

<!-- Ordered by exploitability and impact -->
TEMPLATE

	# SESSIONS.md -- session log
	write_template "${workspace}/SESSIONS.md" <<'TEMPLATE'
# Session Log: {TARGET_NAME}

## Session Template

```markdown
### Session N -- {Date}

- **Operator**: {launcher used}
- **Goals**: what this session aimed to accomplish
- **Findings**: list of findings with IDs (FIND-NNN)
- **Blocked**: what was blocked and why
- **Updated files**: which workspace files were updated
- **Next steps**: what the next session should focus on
```

## Sessions

<!-- Add sessions below in chronological order -->
TEMPLATE


	# Findings database (SQLite)
	init_findings_database "${workspace}" web

	# Exploitation queue
	init_exploitation_queue "${workspace}"

	# Git repository for checkpointing
	init_workspace_git "${workspace}"

	# Replace placeholders in all templates
	for f in FINDINGS.md NOTES.md ENDPOINTS.md ATTACK-SURFACE.md SESSIONS.md; do
		if [[ -f "${workspace}/${f}" ]]; then
			sed -i "s/{TARGET_NAME}/${target_name}/g" "${workspace}/${f}" 2>/dev/null || true
		fi
	done

	log_success "workspace ready: ${workspace}"
}

main() {
	local cmd="${1:-}"
	case "${cmd}" in
	init)
		[[ -n "${2:-}" ]] || error_exit "init requires TARGET_NAME"
		init_workspace "$2" "${3:-}"
		;;
	*)
		usage
		exit 1
		;;
	esac
}

main "$@"
