#!/usr/bin/env bash
# Activate the selected Home output through the guarded generation workflow.
set -euo pipefail
exec "$(dirname "${BASH_SOURCE[0]}")/generation.sh" switch home
