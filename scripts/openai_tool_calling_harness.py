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
    auto_close_sessions: bool = True
    tool_names: Optional[List[str]] = None
    accepts_extra_input: bool = False


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
        description="Open a conversation, read context, draft a reply candidate, and stop for human approval.",
        user_prompt=(
            "Act as a cautious KakaoTalk customer support agent. "
            "Check readiness, inspect one room, read recent messages, and prepare a candidate reply only if it is useful. "
            "Never send a message in this scenario. "
            "If a reply is appropriate, provide a concise approval packet that includes the target room name and the exact reply text to approve. "
            "Close any opened session before finishing."
        ),
        allow_send=False,
        max_turns=10,
    ),
    "approve-send": Scenario(
        name="approve-send",
        description="Send an explicitly approved message after reopening and rechecking the target conversation.",
        user_prompt=(
            "You have explicit approval to send one specific KakaoTalk reply. "
            "Re-check setup, reopen the approved room, fetch recent context, then send exactly the approved message if the room still matches. "
            "Do not invent or rewrite the approved text. "
            "Close the session before finishing."
        ),
        allow_send=True,
        max_turns=8,
        tool_names=[
            "kakao_setup",
            "kakao_status",
            "kakao_room_resolve",
            "kakao_session_open",
            "kakao_session_fetch",
            "kakao_session_reply",
            "kakao_session_close",
        ],
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
    "resolve-room": Scenario(
        name="resolve-room",
        description="Interpret a user-style room request, resolve the intended room carefully, and open it without sending.",
        user_prompt=(
            "The user will provide a natural-language request for a specific KakaoTalk room. "
            "First inspect visible room titles, then resolve the intended room semantically. "
            "Only open the room if one candidate is clearly strongest. "
            "If the intent is ambiguous, stop and explain the candidate rooms instead of guessing. "
            "Do not send any messages. Close any opened session before finishing."
        ),
        allow_send=False,
        max_turns=10,
        accepts_extra_input=True,
    ),
    "recent-summary": Scenario(
        name="recent-summary",
        description="Open one room and summarize the recent conversation history for a user-specified time window.",
        user_prompt=(
            "The user will provide a room request and a recent time window such as the last 3 days. "
            "Resolve the intended room carefully, open it, fetch recent messages, page older messages if needed, "
            "and summarize only the conversation that appears to fall within the requested time window. "
            "If the available transcript is not enough to confidently cover that window, say so explicitly. "
            "Do not send any messages. Close any opened session before finishing."
        ),
        allow_send=False,
        max_turns=12,
        accepts_extra_input=True,
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


def tool_schema(allowed_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    tools = [
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
                "name": "kakao_sessions_list",
                "description": "Inspect stored agent sessions and identify stale ones.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stale_after_minutes": {"type": "integer", "minimum": 0, "maximum": 1440},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "kakao_sessions_cleanup",
                "description": "Clean up stale stored sessions or force-close every stored session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stale_after_minutes": {"type": "integer", "minimum": 0, "maximum": 1440},
                        "force": {"type": "boolean"},
                    },
                    "required": [],
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
    if allowed_names is None:
        return tools
    allowed = set(allowed_names)
    return [tool for tool in tools if tool["function"]["name"] in allowed]


def build_tool_executor(
    allow_send: bool,
    allowed_names: Optional[List[str]] = None,
) -> Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]:
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

    def sessions_list(args: Dict[str, Any]) -> Dict[str, Any]:
        stale_after_minutes = int(args.get("stale_after_minutes", 30))
        return run_json_command(f"--json sessions-list {stale_after_minutes}")

    def sessions_cleanup(args: Dict[str, Any]) -> Dict[str, Any]:
        force = bool(args.get("force", False))
        if force:
            return run_json_command("--json sessions-cleanup --force")
        stale_after_minutes = int(args.get("stale_after_minutes", 30))
        return run_json_command(f"--json sessions-cleanup {stale_after_minutes}")

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

    executors = {
        "kakao_setup": json_cmd("--json setup"),
        "kakao_status": json_cmd("--json status"),
        "kakao_windows": json_cmd("--json windows"),
        "kakao_inbox_scan": inbox_scan,
        "kakao_room_resolve": room_resolve,
        "kakao_session_open": session_open,
        "kakao_session_fetch": session_fetch,
        "kakao_session_reply": session_reply,
        "kakao_session_close": session_close,
        "kakao_sessions_list": sessions_list,
        "kakao_sessions_cleanup": sessions_cleanup,
        "kakao_event_watch_sample": event_watch_sample,
        "kakao_daemon_run_sample": daemon_run_sample,
    }
    if allowed_names is None:
        return executors
    allowed = set(allowed_names)
    return {name: fn for name, fn in executors.items() if name in allowed}


def extract_opened_session_id(result: Dict[str, Any]) -> Optional[str]:
    payload = result.get("json")
    if not isinstance(payload, dict):
        return None
    if payload.get("command") != "session-open" or not payload.get("ok"):
        return None
    session = payload.get("session") or {}
    return session.get("session_id")


def extract_closed_session_id(result: Dict[str, Any], args: Dict[str, Any]) -> Optional[str]:
    payload = result.get("json")
    if isinstance(payload, dict) and payload.get("command") == "session-close" and payload.get("ok"):
        return payload.get("session_id") or args.get("session_id")
    return None


def cleanup_sessions(
    executors: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]],
    open_sessions: List[str],
) -> List[Dict[str, Any]]:
    cleanup_results: List[Dict[str, Any]] = []
    if "kakao_session_close" not in executors:
        return cleanup_results
    close = executors["kakao_session_close"]
    for session_id in list(open_sessions):
        result = close({"session_id": session_id})
        cleanup_results.append(
            {
                "session_id": session_id,
                "result": result,
            }
        )
    return cleanup_results


def run_scenario(
    base_url: str,
    api_key: str,
    model: str,
    scenario: Scenario,
    approved_target: str = "",
    approved_message: str = "",
    extra_input: str = "",
) -> Dict[str, Any]:
    tools = tool_schema(scenario.tool_names)
    executors = build_tool_executor(scenario.allow_send, scenario.tool_names)
    system_prompt = (
        "You are a KakaoTalk operations agent using tool calling. "
        "Use tools to inspect readiness, triage rooms, review conversations, and optionally send replies. "
        "Never invent room names, session ids, or messages that were not observed. "
        "If the environment is blocked, stop and explain the blocker clearly. "
        "Prefer setup before chat actions. "
        "Do not send a reply unless the scenario explicitly allows it. "
        "Keep the final answer concise and operational."
    )
    if not scenario.allow_send:
        system_prompt += " Sending is disabled in this scenario."
    if scenario.name == "safe-reply":
        system_prompt += (
            " You must never call the send tool here. "
            "If a reply is warranted, output an approval packet with the target room and exact draft text."
        )
    if scenario.name == "approve-send":
        system_prompt += (
            " You have already received user approval. "
            "Send only the explicitly approved text after verifying the correct room, then close the session."
        )
    task_payload: Dict[str, Any] = {
        "scenario": {
            "name": scenario.name,
            "description": scenario.description,
            "allow_send": scenario.allow_send,
            "max_turns": scenario.max_turns,
            "auto_close_sessions": scenario.auto_close_sessions,
        },
        "task": scenario.user_prompt,
    }
    if approved_target or approved_message:
        task_payload["approved_send"] = {
            "target": approved_target,
            "message": approved_message,
        }
    if extra_input:
        task_payload["extra_input"] = extra_input
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(task_payload, ensure_ascii=False),
        },
    ]
    transcript: List[Dict[str, Any]] = []
    open_sessions: List[str] = []
    for _ in range(scenario.max_turns):
        response = call_chat_completion(base_url, api_key, model, messages, tools=tools, tool_choice="auto")
        choice = response["choices"][0]
        assistant = choice["message"]
        transcript.append({"assistant": assistant})

        tool_calls = assistant.get("tool_calls") or []
        if not tool_calls:
            cleanup = cleanup_sessions(executors, open_sessions) if scenario.auto_close_sessions else []
            return {
                "scenario": scenario.name,
                "description": scenario.description,
                "final_message": assistant.get("content", ""),
                "transcript": transcript,
                "cleanup": cleanup,
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
            opened_session_id = extract_opened_session_id(result)
            if opened_session_id and opened_session_id not in open_sessions:
                open_sessions.append(opened_session_id)
            closed_session_id = extract_closed_session_id(result, args)
            if closed_session_id and closed_session_id in open_sessions:
                open_sessions.remove(closed_session_id)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    cleanup = cleanup_sessions(executors, open_sessions) if scenario.auto_close_sessions else []
    return {
        "scenario": scenario.name,
        "description": scenario.description,
        "final_message": "Scenario stopped at max_turns without a final assistant message.",
        "transcript": transcript,
        "cleanup": cleanup,
    }


def main(argv: List[str]) -> int:
    if len(argv) >= 2 and argv[1] == "list":
        print(json.dumps({name: scenario.description for name, scenario in SCENARIOS.items()}, ensure_ascii=False, indent=2))
        return 0

    base_url = os.environ.get("LLM_BASE_URL", "http://100.81.203.52:8317/v1")
    model = os.environ.get("LLM_MODEL", "gpt-5.1-codex-mini")
    scenario_name = argv[1] if len(argv) >= 2 else "triage"
    scenario = SCENARIOS.get(scenario_name)
    if not scenario:
        print(json.dumps({"ok": False, "error": f"Unknown scenario: {scenario_name}", "available": list(SCENARIOS)}, ensure_ascii=False, indent=2))
        return 1
    approved_target = argv[2] if len(argv) >= 3 else ""
    approved_message = argv[3] if len(argv) >= 4 else ""
    if scenario_name == "approve-send" and (not approved_target or not approved_message):
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "approve-send requires <target> and <approved_message>",
                    "usage": "python3 scripts/openai_tool_calling_harness.py approve-send <target> <approved_message>",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    extra_input = ""
    if scenario.accepts_extra_input:
        extra_input = " ".join(argv[2:]).strip()
        if not extra_input:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": f"{scenario_name} requires additional user-style input",
                        "usage": {
                            "resolve-room": "python3 scripts/openai_tool_calling_harness.py resolve-room \"여자친구 톡방 열어줘\"",
                            "recent-summary": "python3 scripts/openai_tool_calling_harness.py recent-summary \"애깅 톡방 3일치 대화 내역 조회해서 알려줘\"",
                        }.get(scenario_name, f"python3 scripts/openai_tool_calling_harness.py {scenario_name} \"<request>\""),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        print("LLM_API_KEY is required", file=sys.stderr)
        return 1

    report = {
        "ok": True,
        "runner": str(RUNNER),
        "model": model,
        "base_url": base_url,
        "result": run_scenario(
            base_url,
            api_key,
            model,
            scenario,
            approved_target=approved_target,
            approved_message=approved_message,
            extra_input=extra_input,
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
