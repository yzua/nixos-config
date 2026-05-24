#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TARGET="${SCRIPT_DIR}/agent-iter.sh"
# shellcheck disable=SC1091
source "${REPO_ROOT}/scripts/lib/test-helpers.sh"

assert_true "iter script is executable" test -x "${TARGET}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT

mkdir -p "${tmp_dir}/bin" "${tmp_dir}/counts"
printf 'fake-zai-key\n' >"${tmp_dir}/zai_api_key"

cat >"${tmp_dir}/bin/agent-stub" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

tool="$(basename "$0")"
args_string="$(printf '%q ' "$@")"
printf '%s|ARGS=%s|ANTHROPIC_BASE_URL=%s|OPENCODE_CONFIG_DIR=%s\n' \
  "${tool}" \
  "${args_string% }" \
  "${ANTHROPIC_BASE_URL:-}" \
  "${OPENCODE_CONFIG_DIR:-}" >>"${ITER_LOG_FILE:?}"

count_file="${ITER_COUNT_DIR:?}/${tool}.count"
count=0
if [[ -f "${count_file}" ]]; then
  count="$(cat "${count_file}")"
fi
count=$((count + 1))
printf '%s\n' "${count}" >"${count_file}"

fail_tool="${ITER_FAIL_TOOL:-}"
fail_after="${ITER_FAIL_AFTER:-0}"
fail_code="${ITER_FAIL_CODE:-1}"
if [[ "${tool}" == "${fail_tool}" ]] && (( fail_after > 0 && count >= fail_after )); then
  exit "${fail_code}"
fi
EOF
chmod +x "${tmp_dir}/bin/agent-stub"
ln -s "${tmp_dir}/bin/agent-stub" "${tmp_dir}/bin/claude"
ln -s "${tmp_dir}/bin/agent-stub" "${tmp_dir}/bin/opencode"
ln -s "${tmp_dir}/bin/agent-stub" "${tmp_dir}/bin/codex"
ln -s "${tmp_dir}/bin/agent-stub" "${tmp_dir}/bin/agy"

usage_output="$(bash "${TARGET}" 2>&1 || true)"
assert_contains "${usage_output}" "Usage: iter [count] <agent-alias> [prompt...]" "usage output is shown without arguments"

count_log="${tmp_dir}/counted.log"
: >"${count_log}"
count_output="$({
	PATH="${tmp_dir}/bin:${PATH}" \
		ITER_LOG_FILE="${count_log}" \
		ITER_COUNT_DIR="${tmp_dir}/counts" \
		ZAI_API_KEY_FILE="${tmp_dir}/zai_api_key" \
		bash "${TARGET}" 2 clglm "justsayhi"
} 2>&1)"

count_runs="$(wc -l <"${count_log}" | tr -d ' ')"
assert_eq "${count_runs}" "2" "counted mode runs exact iteration count"
count_log_contents="$(cat "${count_log}")"
assert_contains "${count_log_contents}" "claude|ARGS=--dangerously-skip-permissions --print justsayhi" "claude glm uses headless print mode"
assert_contains "${count_log_contents}" "ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic" "claude glm sets Z.AI base url"
assert_contains "${count_output}" "Iteration 2/2" "counted mode reports iteration progress"

opencode_log="${tmp_dir}/opencode.log"
: >"${opencode_log}"
opencode_output="$({
	PATH="${tmp_dir}/bin:${PATH}" \
		ITER_LOG_FILE="${opencode_log}" \
		ITER_COUNT_DIR="${tmp_dir}/counts" \
		bash "${TARGET}" 2 ocgem "hello world"
} 2>&1)"
opencode_log_contents="$(cat "${opencode_log}")"
assert_contains "${opencode_log_contents}" "opencode|ARGS=run hello\\ world" "opencode uses run subcommand for headless execution"
assert_contains "${opencode_log_contents}" "OPENCODE_CONFIG_DIR=${HOME}/.config/opencode-gemini" "opencode gemini sets profile config dir"
assert_contains "${opencode_output}" "Completed 2/2 iterations" "opencode counted loop completes successfully"

workflow_log="${tmp_dir}/workflow.log"
: >"${workflow_log}"
workflow_output="$({
	PATH="${tmp_dir}/bin:${PATH}" \
		ITER_LOG_FILE="${workflow_log}" \
		ITER_COUNT_DIR="${tmp_dir}/counts" \
		ZAI_API_KEY_FILE="${tmp_dir}/zai_api_key" \
		MARKDOWN_SYNC_PROMPT="sync docs please" \
		bash "${TARGET}" 2 clglmmd
} 2>&1)"
workflow_log_contents="$(cat "${workflow_log}")"
assert_contains "${workflow_log_contents}" "claude|ARGS=--dangerously-skip-permissions --print sync\\ docs\\ please" "workflow alias resolves built-in prompt"
assert_contains "${workflow_output}" "Completed 2/2 iterations" "workflow alias runs to completion"

runtime_perf_log="${tmp_dir}/runtime-perf.log"
: >"${runtime_perf_log}"
runtime_perf_output="$({
	PATH="${tmp_dir}/bin:${PATH}" \
		ITER_LOG_FILE="${runtime_perf_log}" \
		ITER_COUNT_DIR="${tmp_dir}/counts" \
		ZAI_API_KEY_FILE="${tmp_dir}/zai_api_key" \
		RUNTIME_PERFORMANCE_PROMPT="speed up the hot path" \
		bash "${TARGET}" 1 clglmrp
} 2>&1)"
runtime_perf_log_contents="$(cat "${runtime_perf_log}")"
assert_contains "${runtime_perf_log_contents}" "claude|ARGS=--dangerously-skip-permissions --print speed\\ up\\ the\\ hot\\ path" "runtime performance workflow alias resolves built-in prompt"
assert_contains "${runtime_perf_output}" "Completed 1/1 iterations" "runtime performance workflow alias runs to completion"

codex_log="${tmp_dir}/codex.log"
: >"${codex_log}"
codex_output="$({
	PATH="${tmp_dir}/bin:${PATH}" \
		ITER_LOG_FILE="${codex_log}" \
		ITER_COUNT_DIR="${tmp_dir}/counts" \
		bash "${TARGET}" 1 cx "audit again"
} 2>&1)"
codex_log_contents="$(cat "${codex_log}")"
assert_contains "${codex_log_contents}" "codex|ARGS=exec --dangerously-bypass-approvals-and-sandbox audit\\ again" "codex uses exec subcommand for headless execution"
assert_not_contains "${codex_log_contents}" "--no-alt-screen" "codex headless mode skips TUI-only flags"
assert_contains "${codex_output}" "Completed 1/1 iterations" "codex counted loop completes successfully"

set +e
missing_prompt_output="$({
	PATH="${tmp_dir}/bin:${PATH}" \
		ITER_LOG_FILE="${tmp_dir}/missing.log" \
		ITER_COUNT_DIR="${tmp_dir}/counts" \
		ZAI_API_KEY_FILE="${tmp_dir}/zai_api_key" \
		bash "${TARGET}" 2 clglm
} 2>&1)"
missing_prompt_status=$?
set -e
assert_eq "${missing_prompt_status}" "1" "promptless interactive aliases are rejected"
assert_contains "${missing_prompt_output}" "requires a prompt or workflow alias" "promptless aliases get a helpful error"

unlimited_log="${tmp_dir}/unlimited.log"
: >"${unlimited_log}"
set +e
unlimited_output="$({
	PATH="${tmp_dir}/bin:${PATH}" \
		ITER_LOG_FILE="${unlimited_log}" \
		ITER_COUNT_DIR="${tmp_dir}/counts" \
		ITER_FAIL_TOOL="agy" \
		ITER_FAIL_AFTER=3 \
		ITER_FAIL_CODE=17 \
		bash "${TARGET}" ag "keep going"
} 2>&1)"
unlimited_status=$?
set -e

unlimited_runs="$(wc -l <"${unlimited_log}" | tr -d ' ')"
unlimited_log_contents="$(cat "${unlimited_log}")"
assert_eq "${unlimited_status}" "17" "unlimited mode returns failing exit status"
assert_eq "${unlimited_runs}" "3" "unlimited mode repeats until failure"
assert_contains "${unlimited_log_contents}" "agy|ARGS=--dangerously-skip-permissions --prompt keep\\ going" "antigravity uses prompt mode for headless execution"
assert_contains "${unlimited_output}" "Iteration 3/unlimited failed with exit code 17" "unlimited mode reports failure"

# --- Rate-limit retry test ---
# Stub that outputs a 429 error to stderr on first two invocations, then succeeds.
cat >"${tmp_dir}/bin/claude-rl" <<'STUB'
#!/usr/bin/env bash
count_file="${ITER_COUNT_DIR:?}/rl.count"
count=0
[[ -f "${count_file}" ]] && count="$(cat "${count_file}")"
count=$((count + 1))
printf '%s\n' "${count}" >"${count_file}"

if (( count < 3 )); then
  printf 'API Error: 429 {"error":{"code":"1302","message":"Rate limit reached"}}\n' >&2
  exit 1
fi
printf '%s|ARGS=%s\n' "claude" "$(printf '%q ' "$@")" >>"${ITER_LOG_FILE:?}"
STUB
chmod +x "${tmp_dir}/bin/claude-rl"
ln -sf "${tmp_dir}/bin/claude-rl" "${tmp_dir}/bin/claude"

rl_log="${tmp_dir}/rl.log"
: >"${rl_log}"
set +e
rl_output="$({
	ITER_RATE_LIMIT_BASE_WAIT=1 \
	ITER_RATE_LIMIT_RETRIES=3 \
	PATH="${tmp_dir}/bin:${PATH}" \
	ITER_LOG_FILE="${rl_log}" \
	ITER_COUNT_DIR="${tmp_dir}/counts" \
	ZAI_API_KEY_FILE="${tmp_dir}/zai_api_key" \
		bash "${TARGET}" 1 clglm "test prompt"
} 2>&1)"
rl_status=$?
set -e

assert_eq "${rl_status}" "0" "rate-limit retry: succeeds after retries"
assert_contains "${rl_output}" "Rate limit hit (attempt 1/3)" "rate-limit retry: first attempt logged"
assert_contains "${rl_output}" "Rate limit hit (attempt 2/3)" "rate-limit retry: second attempt logged"
assert_contains "${rl_output}" "Completed 1/1 iterations" "rate-limit retry: reports completion"

# --- Rate-limit retry exhaustion test ---
cat >"${tmp_dir}/bin/claude-rlx" <<'STUB2'
#!/usr/bin/env bash
printf '429 Rate limit reached for requests\n' >&2
exit 1
STUB2
chmod +x "${tmp_dir}/bin/claude-rlx"
ln -sf "${tmp_dir}/bin/claude-rlx" "${tmp_dir}/bin/claude"

rlx_log="${tmp_dir}/rlx.log"
: >"${rlx_log}"
set +e
rlx_output="$({
	ITER_RATE_LIMIT_BASE_WAIT=1 \
	ITER_RATE_LIMIT_RETRIES=2 \
	PATH="${tmp_dir}/bin:${PATH}" \
	ITER_LOG_FILE="${rlx_log}" \
	ITER_COUNT_DIR="${tmp_dir}/counts" \
	ZAI_API_KEY_FILE="${tmp_dir}/zai_api_key" \
		bash "${TARGET}" clglm "test"
} 2>&1)"
rlx_status=$?
set -e
assert_eq "${rlx_status}" "2" "rate-limit exhaustion: exits with rate-limit code"
assert_contains "${rlx_output}" "Rate-limit retry limit (2) exceeded" "rate-limit exhaustion: reports limit exceeded"

# Restore normal claude symlink
ln -sf "${tmp_dir}/bin/agent-stub" "${tmp_dir}/bin/claude"

echo "All agent iter tests passed."
