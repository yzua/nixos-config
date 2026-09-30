#!/usr/bin/env bash
# Build and review the selected Home output through the generation workflow.
set -euo pipefail
exec "$(dirname "${BASH_SOURCE[0]}")/generation.sh" preview home
