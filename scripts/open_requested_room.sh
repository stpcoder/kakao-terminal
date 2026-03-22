#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/harness_common.sh"

if [[ $# -lt 1 ]]; then
  cat <<'EOF' >&2
Usage:
  scripts/open_requested_room.sh "<user room request>"

Examples:
  scripts/open_requested_room.sh "여자친구 톡방 열어줘"
  scripts/open_requested_room.sh "윤수원 톡방 들어가줘"
EOF
  exit 1
fi

run_kakao_agent_scenario resolve-room "$@"
