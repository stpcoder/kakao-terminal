#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/harness_common.sh"

if [[ $# -lt 1 ]]; then
  cat <<'EOF' >&2
Usage:
  scripts/run_kakao_agent_scenario.sh <triage|review|safe-reply|approve-send|monitor|resolve-room|recent-summary> [args...]
EOF
  exit 1
fi

run_kakao_agent_scenario "$@"
