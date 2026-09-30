#!/usr/bin/env bash
# Evaluate active, saved, and desired generations without building or activating.
set -euo pipefail
exec "$(dirname "${BASH_SOURCE[0]}")/generation.sh" status
