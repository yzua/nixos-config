#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/lib/test-helpers.sh"

# Source launcher once (AI_AGENT_LAUNCHER_SOURCE_ONLY prevents main from running).
# shellcheck disable=SC1091
AI_AGENT_LAUNCHER_SOURCE_ONLY=1 source "${SCRIPT_DIR}/agent-launcher.sh"

launcher_output="$(workflow_display_lines 2>&1)"

assert_contains "${launcher_output}" "commit split (cm) — Splits working tree into logical commits with validated, minimal staging." "workflow picker shows commit split label"
assert_contains "${launcher_output}" "refactor maintainability (rf) — Improves structure and clarity without changing behavior, APIs, or workflows." "workflow picker shows refactor label"
assert_contains "${launcher_output}" "dependency upgrade (du) — Upgrades dependencies safely, handles breaking changes, validates compatibility, reports blockers." "workflow picker shows dependency upgrade label"
assert_contains "${launcher_output}" "runtime performance (rp) — Measures real code-path bottlenecks, applies low-risk optimizations, and verifies before-and-after latency, throughput, or memory gains." "workflow picker shows runtime performance label"

commit_suffix="$(workflow_suffix_from_selection "commit split (cm) — Splits working tree into logical commits with validated, minimal staging." 2>&1)"
assert_eq "${commit_suffix}" "cm" "workflow label maps back to cm suffix"

none_suffix="$(workflow_suffix_from_selection "none" 2>&1)"
assert_eq "${none_suffix}" "none" "none label maps back to none suffix"

runtime_perf_suffix="$(workflow_suffix_from_selection "runtime performance (rp) — Measures real code-path bottlenecks, applies low-risk optimizations, and verifies before-and-after latency, throughput, or memory gains." 2>&1)"
assert_eq "${runtime_perf_suffix}" "rp" "workflow label maps back to rp suffix"

for alias_name in "${LAUNCHER_SIMPLE_ALIASES[@]}"; do
	assert_true "simple picker alias is registered: ${alias_name}" is_supported_base_alias "${alias_name}"
done

echo "All agent launcher tests passed."
