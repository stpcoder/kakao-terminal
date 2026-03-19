#!/usr/bin/env python3
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / ".claude" / "skills" / "kakao-terminal" / "scripts" / "run.py"


@dataclass
class Scenario:
    name: str
    description: str
    user_prompt: str
    allow_send: bool = False
    max_turns: int = 8


SCENARIOS: Dict[str, Scenario] = {
    "triage": Scenario(
        name="triage",
        description="Check readiness, inspect inbox, and identify the next room worth handling.",
        user_prompt=(
            "You are triaging KakaoTalk customer conversations. "
            "Verify setup first, inspect inbox state, and if possible open one promising room "
            "to summarize what needs attention next. Do not send any messages."
        ),
        allow_send=False,
    ),
    "review": Scenario(
        name="review",
        description="Resolve a target room, open it, and read the current conversation safely.",
        user_prompt=(
            "Review the current KakaoTalk conversation for a customer room. "
            "Use setup and discovery first if needed, then open one room and fetch recent messages. "
            "Do not send any messages."
        ),
        allow_send=False,
    ),
    "safe-reply": Scenario(
        name="safe-reply",
        description="Open a conversation, read context, and send only if the scenario explicitly allows it.",
        user_prompt=(
            "Act as a cautious KakaoTalk customer support agent. "
            "Check readiness, inspect one room, read recent messages, and only send if it is clearly safe "
            "and explicitly allowed by the scenario."
        ),
        allow_send=True,
        max_turns=10,
    ),
    "monitor": Scenario(
        name="monitor",
        description="Exercise the long-running monitoring surface with event-watch or daemon-run samples.",
        user_prompt=(
            "Validate the KakaoTalk monitoring surface. Prefer setup first, then use daemon-run or event-watch "
            "sampling to confirm event output. Do not send any messages."
        ),
        allow_send=False,
        max_turns=6,
    ),
}


def call_chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: str = "auto",
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=f"{base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize_command_args(command_args: str) -> str:
    parts = shlex.split(command_args)
    runner_str = str(RUNNER)
    if parts and parts[0] == "python3":
        if len(parts) >= 2 and parts[1] in {runner_str, ".claude/skills/kakao-terminal/scripts/run.py"}:
            parts = parts[2:]
    elif parts and parts[0] in {runner_str, ".claude/skills/kakao-terminal/scripts/run.py"}:
        parts = parts[1:]
    return shlex.join(parts)


def run_json_command(command_args: str) -> Dict[str, Any]:
    normalized = normalize_command_args(command_args)
    cmd = ["python3", str(RUNNER)] + shlex.split(normalized)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
    stdout = proc.stdout.strip()
    payload = None
    try:
        payload = json.loads(stdout) if stdout else None
    except json.JSONDecodeError:
        payload = None
    return {
        "command": normalized,
        "argv": cmd,
        "returncode": proc.returncode,
        "stdout": stdout,
        "stderr": proc.stderr.strip(),
        "json": payload,
    }


def sample_stream(command_args: str, max_lines: int = 3, timeout_sec: int = 15) -> Dict[str, Any]:
    normalized = normalize_command_args(command_args)
    cmd = ["python3", str(RUNNER)] + shlex.split(normalized)
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lines: List[str] = []
    started = time.time()
    try:
        while len(lines) < max_lines and (time.time() - started) < timeout_sec:
            line = proc.stdout.readline()
            if not line:
                break
            lines.append(line.rstrip("\n"))
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    finally:
        stderr = proc.stderr.read().strip() if proc.stderr else ""
    events = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"raw": line})
    return {
        "command": normalized,
        "argv": cmd,
        "stdout_lines": lines,
        "stderr": stderr,
        "events": events,
    }


def tool_schema() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "kakao_setup",
                "description": "Check KakaoTalk prerequisites before any other action.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kakao_status",
                "description": "Read current connection and session state.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kakao_windows",
                "description": "Inspect currently visible KakaoTalk windows.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kakao_inbox_scan",
                "description": "Scan the inbox and return room candidates with structured JSON.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                        "offset": {"type": "integer", "minimum": 0, "maximum": 100},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kakao_room_resolve",
                "description": "Resolve a user-facing room query to a concrete room.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kakao_session_open",
                "description": "Open a room as an agent session and fetch an initial snapshot.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["target"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kakao_session_fetch",
                "description": "Fetch latest, older, newer, or refresh messages for a session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "mode": {"type": "string", "enum": ["latest", "refresh", "older", "newer"]},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                        "step": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kakao_session_reply",
                "description": "Send a message safely to a previously opened session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["session_id", "message"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kakao_session_close",
                "description": "Close and release a previously opened session.",
                "parameters": {
                    "type": "object",
                    "properties": {"session_id": {"type": "string"}},
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kakao_event_watch_sample",
                "description": "Run event-watch briefly and return a small sample of NDJSON events.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "interval": {"type": "integer", "minimum": 1, "maximum": 30},
                        "count": {"type": "integer", "minimum": 1, "maximum": 20},
                        "heartbeat": {"type": "integer", "minimum": 1, "maximum": 60},
                        "sample_lines": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": ["session_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kakao_daemon_run_sample",
                "description": "Run daemon-run briefly and return a small sample of NDJSON events.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "interval": {"type": "integer", "minimum": 1, "maximum": 30},
                        "room_limit": {"type": "integer", "minimum": 1, "maximum": 20},
                        "watch_count": {"type": "integer", "minimum": 1, "maximum": 20},
                        "heartbeat": {"type": "integer", "minimum": 1, "maximum": 60},
                        "sample_lines": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
    ]


def build_tool_executor(allow_send: bool) -> Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]:
    def json_cmd(command: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        def runner(_: Dict[str, Any]) -> Dict[str, Any]:
            return run_json_command(command)
        return runner

    def inbox_scan(args: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(args.get("limit", 8))
        offset = int(args.get("offset", 0))
        return run_json_command(f"--json inbox-scan {limit} {offset}")

    def room_resolve(args: Dict[str, Any]) -> Dict[str, Any]:
        query = args["query"]
        return run_json_command(f"--json room-resolve {shlex.quote(query)}")

    def session_open(args: Dict[str, Any]) -> Dict[str, Any]:
        target = args["target"]
        limit = int(args.get("limit", 20))
        return run_json_command(f"--json session-open {shlex.quote(target)} {limit}")

    def session_fetch(args: Dict[str, Any]) -> Dict[str, Any]:
        session_id = args["session_id"]
        mode = args.get("mode", "latest")
        limit = int(args.get("limit", 20))
        step = int(args.get("step", 10))
        return run_json_command(f"--json session-fetch {shlex.quote(session_id)} {mode} {limit} {step}")

    def session_reply(args: Dict[str, Any]) -> Dict[str, Any]:
        if not allow_send:
            return {"blocked": True, "message": "Sending is disabled for this scenario."}
        session_id = args["session_id"]
        message = args["message"]
        return run_json_command(f"--json session-reply {shlex.quote(session_id)} {shlex.quote(message)}")

    def session_close(args: Dict[str, Any]) -> Dict[str, Any]:
        session_id = args["session_id"]
        return run_json_command(f"--json session-close {shlex.quote(session_id)}")

    def event_watch_sample(args: Dict[str, Any]) -> Dict[str, Any]:
        session_id = args["session_id"]
        interval = int(args.get("interval", 3))
        count = int(args.get("count", 5))
        heartbeat = int(args.get("heartbeat", 15))
        sample_lines = int(args.get("sample_lines", 3))
        return sample_stream(
            f"event-watch {shlex.quote(session_id)} {interval} {count} {heartbeat}",
            max_lines=sample_lines,
        )

    def daemon_run_sample(args: Dict[str, Any]) -> Dict[str, Any]:
        interval = int(args.get("interval", 5))
        room_limit = int(args.get("room_limit", 10))
        watch_count = int(args.get("watch_count", 5))
        heartbeat = int(args.get("heartbeat", 15))
        sample_lines = int(args.get("sample_lines", 3))
        return sample_stream(
            f"daemon-run {interval} {room_limit} {watch_count} {heartbeat}",
            max_lines=sample_lines,
        )

    return {
        "kakao_setup": json_cmd("--json setup"),
        "kakao_status": json_cmd("--json status"),
        "kakao_windows": json_cmd("--json windows"),
        "kakao_inbox_scan": inbox_scan,
        "kakao_room_resolve": room_resolve,
        "kakao_session_open": session_open,
        "kakao_session_fetch": session_fetch,
        "kakao_session_reply": session_reply,
        "kakao_session_close": session_close,
        "kakao_event_watch_sample": event_watch_sample,
        "kakao_daemon_run_sample": daemon_run_sample,
    }


def run_scenario(base_url: str, api_key: str, model: str, scenario: Scenario) -> Dict[str, Any]:
    tools = tool_schema()
    executors = build_tool_executor(scenario.allow_send)
    system_prompt = (
        "You are a KakaoTalk operations agent using tool calling. "
        "Use tools to inspect readiness, triage rooms, review conversations, and optionally send replies. "
        "Never invent room names, session ids, or messages that were not observed. "
        "If the environment is blocked, stop and explain the blocker clearly. "
        "Prefer setup before chat actions. "
        "Do not send a reply unless the scenario explicitly allows it. "
        "Keep the final answer concise and operational."
    )
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "scenario": {
                        "name": scenario.name,
                        "description": scenario.description,
                        "allow_send": scenario.allow_send,
                        "max_turns": scenario.max_turns,
                    },
                    "task": scenario.user_prompt,
                },
                ensure_ascii=False,
            ),
        },
    ]
    transcript: List[Dict[str, Any]] = []
    for _ in range(scenario.max_turns):
        response = call_chat_completion(base_url, api_key, model, messages, tools=tools, tool_choice="auto")
        choice = response["choices"][0]
        assistant = choice["message"]
        transcript.append({"assistant": assistant})

        tool_calls = assistant.get("tool_calls") or []
        if not tool_calls:
            return {
                "scenario": scenario.name,
                "description": scenario.description,
                "final_message": assistant.get("content", ""),
                "transcript": transcript,
            }

        messages.append(
            {
                "role": "assistant",
                "content": assistant.get("content"),
                "tool_calls": tool_calls,
            }
        )
        for tool_call in tool_calls:
            name = tool_call["function"]["name"]
            raw_args = tool_call["function"].get("arguments") or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {"_raw_arguments": raw_args}
            result = executors[name](args)
            transcript.append({"tool_call": {"name": name, "arguments": args, "result": result}})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    return {
        "scenario": scenario.name,
        "description": scenario.description,
        "final_message": "Scenario stopped at max_turns without a final assistant message.",
        "transcript": transcript,
    }


def main(argv: List[str]) -> int:
    if len(argv) >= 2 and argv[1] == "list":
        print(json.dumps({name: scenario.description for name, scenario in SCENARIOS.items()}, ensure_ascii=False, indent=2))
        return 0

    base_url = os.environ.get("LLM_BASE_URL", "http://100.81.203.52:8317/v1")
    api_key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL", "gpt-5.1-codex-mini")
    if not api_key:
        print("LLM_API_KEY is required", file=sys.stderr)
        return 1

    scenario_name = argv[1] if len(argv) >= 2 else "triage"
    scenario = SCENARIOS.get(scenario_name)
    if not scenario:
        print(json.dumps({"ok": False, "error": f"Unknown scenario: {scenario_name}", "available": list(SCENARIOS)}, ensure_ascii=False, indent=2))
        return 1

    report = {
        "ok": True,
        "runner": str(RUNNER),
        "model": model,
        "base_url": base_url,
        "result": run_scenario(base_url, api_key, model, scenario),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
