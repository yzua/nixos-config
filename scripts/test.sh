#!/usr/bin/env bash
# Run the explicitly offline regression suites, never activation or live lab checks.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

for tool in python3 just bun node nix git tmux herdr niri; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'Missing regression prerequisite: %s. Run from nix develop with the managed apps available.\n' "$tool" >&2
    exit 1
  fi
done
if [[ -n "${PI_BIN:-}" ]]; then
  [[ -x "$PI_BIN" ]] || {
    printf 'PI_BIN is not executable: %s\n' "$PI_BIN" >&2
    exit 1
  }
elif ! command -v pi >/dev/null 2>&1; then
  echo 'Pi is required for loader regressions; install the managed profile or set PI_BIN.' >&2
  exit 1
fi

python3 -B - <<'PY'
import os
from pathlib import Path

extensions = Path(os.environ.get("PI_WEB_FETCH_DIR", Path.home() / ".pi/agent/extensions/web-fetch"))
if not (extensions / "node_modules").is_dir():
    raise SystemExit("Managed web-fetch dependencies are required; set PI_WEB_FETCH_DIR to test another installation.")
PY

bash tests/workflow.sh
node --test tests/pi-subagents-recall.test.mjs
for suite in \
  config-artifacts voice-action pi-config pi-subagents pi-extensions pi-herdr \
  pi-resume-dispatch pi-herdr-reporting \
  pi-re-config pi-re-rea pi-re-android pi-re-runtime pi-re-traffic pi-re-subagent pi-re-lab; do
  printf '\n== %s ==\n' "$suite"
  python3 -B "tests/$suite.py"
done
