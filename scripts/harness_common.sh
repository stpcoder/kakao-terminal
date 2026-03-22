#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HARNESS_PY="${REPO_ROOT}/scripts/openai_tool_calling_harness.py"
SSH_KEY="/Users/taehoje/.personal-info/keys/ssh/oracle_ssh.key"
API_KEY_HOST="ubuntu@168.107.23.157"
API_KEY_PATH="/opt/cliproxyapi/API_KEY.txt"

export LLM_BASE_URL="${LLM_BASE_URL:-http://100.81.203.52:8317/v1}"
export LLM_MODEL="${LLM_MODEL:-gpt-5.1-codex-mini}"

ensure_llm_api_key() {
  if [[ -n "${LLM_API_KEY:-}" ]]; then
    return 0
  fi

  if [[ ! -f "${SSH_KEY}" ]]; then
    echo "Missing SSH key at ${SSH_KEY}" >&2
    return 1
  fi

  LLM_API_KEY="$(
    ssh -i "${SSH_KEY}" -o StrictHostKeyChecking=accept-new "${API_KEY_HOST}" "cat '${API_KEY_PATH}'"
  )"
  export LLM_API_KEY
}

run_kakao_agent_scenario() {
  local scenario="$1"
  shift || true
  ensure_llm_api_key
  cd "${REPO_ROOT}"
  python3 "${HARNESS_PY}" "${scenario}" "$@"
}

