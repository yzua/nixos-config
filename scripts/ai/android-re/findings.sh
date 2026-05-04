#!/usr/bin/env bash
set -euo pipefail
# SQLite findings database CLI for Android RE workspaces.
# Usage: findings.sh <command> <workspace> [args...]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/lib/logging.sh"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/lib/require.sh"

trap 'log_error "command failed at line ${LINENO}: ${BASH_COMMAND}"' ERR

FINDINGS_USAGE_NAME="findings.sh"
FINDINGS_LIST_VULNS_COLUMNS="finding_id, title, severity, owasp, status, confidence"
FINDINGS_SCHEMA_KIND="android"

# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/ai/_findings-common.sh"

findings_main "$@"
