#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/harness_common.sh"

if [[ $# -lt 2 ]]; then
  cat <<'EOF' >&2
Usage:
  scripts/approve_send.sh "<room target>" "<approved message>"
EOF
  exit 1
fi

run_kakao_agent_scenario approve-send "$@"
