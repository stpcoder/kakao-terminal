#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"
python3 - <<'PY'
import json
from scripts.openai_tool_calling_harness import tool_schema

tools = []
for entry in tool_schema():
    fn = entry["function"]
    tools.append(
        {
            "name": fn["name"],
            "description": fn["description"],
            "parameters": fn["parameters"],
        }
    )

print(json.dumps(tools, ensure_ascii=False, indent=2))
PY
