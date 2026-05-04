#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/lib/logging.sh"

trap 'log_error "command failed at line ${LINENO}: ${BASH_COMMAND}"' ERR

DOCS_ROOT="${DOCS_ROOT:-${HOME}/Documents}"

# shellcheck source=scripts/ai/android-re/_helpers.sh
source "${SCRIPT_DIR}/_helpers.sh"
# shellcheck source=scripts/ai/_workspace-init-common.sh
source "${REPO_ROOT}/scripts/ai/_workspace-init-common.sh"

usage() {
	cat <<'EOF'
Usage: workspace-init.sh <command> [args]

Commands:
  init PACKAGE_NAME [APK_PATH]   Create target workspace at ~/Documents/<name>
EOF
}

init_workspace() {
	local package_name="$1"
	local apk_path="${2:-}"
	local workspace="${DOCS_ROOT}/${package_name}"

	log_info "initializing workspace at ${workspace}"
	mkdir -p "${workspace}"/{scripts,evidence/{screenshots,logs,pcaps},analysis}

	# README.md — target overview
	write_template "${workspace}/README.md" <<'TEMPLATE'
# {APP_NAME}

## Target Metadata

| Field | Value |
|-------|-------|
| Package | `{package_name}` |
| Version | _to be filled_ |
| ABI | _to be filled_ |
| SHA-256 | _to be filled on init if APK provided_ |
| Init date | _to be filled on init_ |
| Scope | Full assessment: static + dynamic + network + runtime |

## Session Log

See [SESSIONS.md](SESSIONS.md) for per-session history.

## Quick Links

- [Findings](FINDINGS.md)
- [Endpoints](ENDPOINTS.md)
- [Anti-Analysis Defenses](ANTI-ANALYSIS.md)
- [Exported Components](COMPONENTS.md)
- [Attack Surface Map](ATTACK-SURFACE.md)
- [Running Notes](NOTES.md)
TEMPLATE

	# FINDINGS.md — OWASP Mobile Top 10 classified
	write_template "${workspace}/FINDINGS.md" <<'TEMPLATE'
# Findings: {APP_NAME}

## Severity Definitions

| Severity | Criteria |
|----------|----------|
| Critical | Remote code execution, auth bypass, data breach with no user interaction |
| High | Privilege escalation, sensitive data exposure, auth bypass requiring user interaction |
| Medium | Limited data leak, DoS, info disclosure requiring specific conditions |
| Low | Minor info leak, best practice violations, low-impact issues |
| Info | Observations useful for context but not directly exploitable |

## M1: Improper Credential Usage

<!-- Hardcoded credentials, API keys in source, credential leakage -->

## M2: Inadequate Supply Chain Security

<!-- Outdated vulnerable SDKs, unsigned code, insecure update mechanisms -->

## M3: Insecure Authentication/Authorization

<!-- Auth bypass, weak session management, missing auth on endpoints -->

## M4: Insufficient Input/Output Validation

<!-- Deep link injection, intent manipulation, WebView XSS, content provider SQLi -->

## M5: Insecure Communication

<!-- Cleartext traffic, weak TLS, certificate pinning issues, QUIC bypass -->

## M6: Inadequate Privacy Controls

<!-- PII leakage, excessive permissions, tracking without consent -->

## M7: Insufficient Binary Protections

<!-- No obfuscation, debuggable release, hardcoded secrets in binary -->

## M8: Security Misconfiguration

<!-- Misconfigured network security config, exported components, permissive backups -->

## M9: Insecure Data Storage

<!-- Plaintext tokens in SharedPreferences, credentials in SQLite, insecure file perms -->

## M10: Insufficient Cryptography

<!-- Weak crypto algorithms, hardcoded keys, improper IV usage, custom crypto -->

---

## Finding Template

```markdown
### FIND-NNN: {Title}

- **Severity**: Critical/High/Medium/Low/Info
- **OWASP**: M?
- **MASVS**: MASVS-???
- **Status**: Confirmed / Investigating / False Positive
- **Location**: file/class/method/endpoint
- **Impact**: what attacker can achieve
- **Evidence**: screenshot path, log line, request, hook output
- **Repro**: numbered steps
- **Remediation**: suggested fix
```
TEMPLATE

	# NOTES.md — running notes
	write_template "${workspace}/NOTES.md" <<'TEMPLATE'
# Notes: {APP_NAME}

## Observations

<!-- General observations about the app, its architecture, and behavior -->

## Hypotheses

<!-- Unverified theories to investigate. Format: H1: description [status] -->

## Blocked Items

<!-- Things that are blocked and why. Include the specific blocker and potential bypass. -->

## Next Steps

<!-- Ordered list of what to investigate next session -->
TEMPLATE

	# ENDPOINTS.md — API surface
	write_template "${workspace}/ENDPOINTS.md" <<'TEMPLATE'
# Endpoints: {APP_NAME}

## API Base URLs

<!-- Discovered base URLs: production, staging, debug -->

## Authentication Endpoints

| Method | URL | Purpose | Auth Required | Notes |
|--------|-----|---------|---------------|-------|

## API Endpoints

| Method | URL | Purpose | Auth Required | Params | Notes |
|--------|-----|---------|---------------|--------|-------|

## Backend Services

<!-- Firebase, custom APIs, CDN, analytics endpoints, push notification services -->
TEMPLATE

	# ANTI-ANALYSIS.md — defenses
	write_template "${workspace}/ANTI-ANALYSIS.md" <<'TEMPLATE'
# Anti-Analysis Defenses: {APP_NAME}

## Defense Summary

| Defense Type | Detected | Bypassed | Method | Notes |
|-------------|----------|----------|--------|-------|
| Root detection | ? | ? | | |
| Emulator detection | ? | ? | | |
| Frida detection | ? | ? | | |
| Certificate pinning | ? | ? | | |
| Debugger detection | ? | ? | | |
| Obfuscation | ? | ? | | |
| Integrity checks | ? | ? | | |
| Native guards | ? | ? | | |

## Details

### Root Detection

<!-- Classes, methods, file checks, native probes -->

### Emulator Detection

<!-- Build fields, file paths, sensor checks, timing, native -->

### Frida Detection

<!-- Port scanning, process name, class name checks, timing -->

### Certificate Pinning

<!-- Implementation: OkHttp CertificatePinner, custom TrustManager, native SSL -->

### Other Defenses

<!-- Obfuscator used, tamper detection, integrity verification -->
TEMPLATE

	# COMPONENTS.md — exported components
	write_template "${workspace}/COMPONENTS.md" <<'TEMPLATE'
# Exported Components: {APP_NAME}

## Activities

| Name | Exported | Intent Filters | Auto-Verify | Notes |
|------|----------|----------------|-------------|-------|

## Services

| Name | Exported | Intent Filters | Permission | Notes |
|------|----------|----------------|------------|-------|

## Broadcast Receivers

| Name | Exported | Intent Filters | Permission | Notes |
|------|----------|----------------|------------|-------|

## Content Providers

| Name | Exported | Authority | Permission | Grant URIs | Notes |
|------|----------|-----------|------------|------------|-------|

## Deep Links

| Scheme | Host | Path Pattern | Target | Notes |
|--------|------|-------------|--------|-------|

## Test Results

<!-- For each component: what was tested, what happened, whether it's exploitable -->
TEMPLATE

	# ATTACK-SURFACE.md
	write_template "${workspace}/ATTACK-SURFACE.md" <<'TEMPLATE'
# Attack Surface: {APP_NAME}

## Entry Points

<!-- External inputs: deep links, intents, file handlers, WebView URLs, push notifications -->

## Network Surface

<!-- API endpoints, WebSocket connections, custom protocols, backend services -->

## Local Surface

<!-- SharedPreferences, SQLite, files, content providers, backup data -->

## IPC Surface

<!-- Exported components, AIDL services, Messengers, broadcast receivers -->

## Trust Boundaries

<!-- Where does the app trust external input? Where are auth checks enforced? -->

## Risk Ranking

<!-- Ordered by exploitability and impact -->
TEMPLATE

	# SESSIONS.md — session log
	write_template "${workspace}/SESSIONS.md" <<'TEMPLATE'
# Session Log: {APP_NAME}

## Session Template

```markdown
### Session N — {Date}

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
	init_findings_database "${workspace}" android

	# Exploitation queue
	init_exploitation_queue "${workspace}"

	# Git repository for checkpointing
	init_workspace_git "${workspace}"

	# Record metadata if APK provided
	if [[ -n "${apk_path}" && -f "${apk_path}" ]]; then
		local sha256
		sha256="$(sha256sum "${apk_path}" | awk '{print $1}')"
		local init_date
		init_date="$(date -I)"
		local readme="${workspace}/README.md"
		sed -i "s/{package_name}/${package_name}/g" "${readme}"
		sed -i "s/_to be filled on init if APK provided_/${sha256}/" "${readme}"
		sed -i "s/_to be filled on init_/${init_date}/" "${readme}"
		log_success "APK hash recorded: ${sha256:0:16}..."
	fi

	# Replace placeholder in all templates
	for f in FINDINGS.md NOTES.md ENDPOINTS.md ANTI-ANALYSIS.md COMPONENTS.md ATTACK-SURFACE.md SESSIONS.md; do
		if [[ -f "${workspace}/${f}" ]]; then
			sed -i "s/{APP_NAME}/${package_name}/g" "${workspace}/${f}" 2>/dev/null || true
		fi
	done
	sed -i "s/{package_name}/${package_name}/g" "${workspace}/README.md" 2>/dev/null || true

	log_success "workspace ready: ${workspace}"
}

main() {
	local cmd="${1:-}"
	case "${cmd}" in
	init)
		[[ -n "${2:-}" ]] || error_exit "init requires PACKAGE_NAME"
		init_workspace "$2" "${3:-}"
		;;
	*)
		usage
		exit 1
		;;
	esac
}

main "$@"
