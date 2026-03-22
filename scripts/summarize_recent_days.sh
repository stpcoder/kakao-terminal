#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/harness_common.sh"

if [[ $# -lt 1 ]]; then
  cat <<'EOF' >&2
Usage:
  scripts/summarize_recent_days.sh "<room request and time window>"

Examples:
  scripts/summarize_recent_days.sh "애깅❣️ 톡방 3일치 대화 내역 조회해서 알려줘"
  scripts/summarize_recent_days.sh "윤수원 톡방 최근 3일 대화 요약해줘"
EOF
  exit 1
fi

run_kakao_agent_scenario recent-summary "$@"
