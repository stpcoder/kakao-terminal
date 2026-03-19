#!/usr/bin/env python3
import json
import os
import shlex
import subprocess
import sys
import textwrap
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / ".claude" / "skills" / "kakao-terminal" / "scripts" / "run.py"


@dataclass
class Scenario:
    name: str
    goal: str
    available_commands: List[str]
    max_steps: int = 4
    require_ok: bool = True
    summary: Dict[str, Any] = field(default_factory=dict)


def call_chat_completion(base_url: str, api_key: str, model: str, messages: List[Dict[str, str]]) -> str:
    payload = {
        "model": model,
        "temperature": 0,
        "messages": messages,
    }
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
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def ask_next_action(base_url: str, api_key: str, model: str, scenario: Scenario, transcript: List[Dict[str, Any]]) -> Dict[str, Any]:
    system = textwrap.dedent(
        """\
        You are evaluating a KakaoTalk skill runner. Choose exactly one next shell command to run.
        Rules:
        - Use only commands explicitly listed in the scenario.
        - Commands must be arguments for: python3 .claude/skills/kakao-terminal/scripts/run.py
        - Prefer high-level JSON commands.
        - If the scenario is blocked by environment state, return a final verdict instead of inventing work.
        - Return strict JSON only with keys:
          action: "run" or "done"
          command: string (only when action is "run")
          reason: short string
          verdict: "pass" | "fail" | "blocked" | "partial" (only when action is "done")
        """
    )
    user = {
        "scenario": {
            "name": scenario.name,
            "goal": scenario.goal,
            "available_commands": scenario.available_commands,
            "max_steps": scenario.max_steps,
        },
        "transcript": transcript,
    }
    raw = call_chat_completion(
        base_url,
        api_key,
        model,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
    )
    return json.loads(raw)


def normalize_command_args(command_args: str) -> str:
    parts = shlex.split(command_args)
    if not parts:
        return command_args
    runner_str = str(RUNNER)
    if parts[0] == "python3":
        if len(parts) >= 2 and (parts[1] == runner_str or parts[1] == ".claude/skills/kakao-terminal/scripts/run.py"):
            parts = parts[2:]
    elif parts[0] == runner_str or parts[0] == ".claude/skills/kakao-terminal/scripts/run.py":
        parts = parts[1:]
    return shlex.join(parts)


def run_skill_command(command_args: str) -> Dict[str, Any]:
    normalized = normalize_command_args(command_args)
    cmd = ["python3", str(RUNNER)] + shlex.split(normalized)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=90)
    stdout = proc.stdout.strip()
    payload = None
    try:
        payload = json.loads(stdout) if stdout else None
    except json.JSONDecodeError:
        payload = None
    return {
        "argv": cmd,
        "normalized_command": normalized,
        "returncode": proc.returncode,
        "stdout": stdout,
        "stderr": proc.stderr.strip(),
        "json": payload,
    }


def run_stream_command(command_args: str, lines: int = 2, timeout_sec: int = 12) -> Dict[str, Any]:
    normalized = normalize_command_args(command_args)
    cmd = ["python3", str(RUNNER)] + shlex.split(normalized)
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out_lines: List[str] = []
    try:
        for _ in range(lines):
            line = proc.stdout.readline()
            if not line:
                break
            out_lines.append(line.rstrip("\n"))
        proc.terminate()
        try:
            proc.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            proc.kill()
    finally:
        stderr = proc.stderr.read().strip() if proc.stderr else ""
    parsed = []
    for line in out_lines:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            parsed.append({"raw": line})
    return {
        "argv": cmd,
        "normalized_command": normalized,
        "stdout_lines": out_lines,
        "stderr": stderr,
        "events": parsed,
    }


def evaluate_scenario(base_url: str, api_key: str, model: str, scenario: Scenario) -> Dict[str, Any]:
    transcript: List[Dict[str, Any]] = []
    for _ in range(scenario.max_steps):
        decision = ask_next_action(base_url, api_key, model, scenario, transcript)
        transcript.append({"decision": decision})
        if decision["action"] == "done":
            return {
                "name": scenario.name,
                "goal": scenario.goal,
                "verdict": decision["verdict"],
                "reason": decision["reason"],
                "transcript": transcript,
            }
        result = run_skill_command(decision["command"])
        transcript.append({"result": result})

        payload = result.get("json") or {}
        if payload.get("ok") is True and scenario.require_ok and payload.get("command"):
            if scenario.name == "setup_and_discovery" and payload.get("command") in {"setup", "inbox-scan", "windows"}:
                if payload.get("command") == "inbox-scan":
                    return {
                        "name": scenario.name,
                        "goal": scenario.goal,
                        "verdict": "pass",
                        "reason": "Structured discovery command succeeded.",
                        "transcript": transcript,
                    }
        if payload.get("ok") is False:
            message = ((payload.get("error") or {}).get("message") or "").lower()
            if "no kakaotalk windows found" in message:
                return {
                    "name": scenario.name,
                    "goal": scenario.goal,
                    "verdict": "blocked",
                    "reason": "KakaoTalk process is running but no windows are exposed to the skill runner.",
                    "transcript": transcript,
                }
    return {
        "name": scenario.name,
        "goal": scenario.goal,
        "verdict": "partial",
        "reason": "Scenario hit the step limit without a clean pass/fail decision.",
        "transcript": transcript,
    }


def main() -> int:
    base_url = os.environ.get("LLM_BASE_URL", "http://100.81.203.52:8317/v1")
    api_key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL", "gpt-5.1-codex-mini")
    if not api_key:
        print(json.dumps({"ok": False, "error": "LLM_API_KEY is required"}, ensure_ascii=False, indent=2))
        return 1

    scenarios = [
        Scenario(
            name="setup_and_discovery",
            goal="Verify the skill runner can check prerequisites and attempt structured inbox discovery.",
            available_commands=[
                "--json setup",
                "--json status",
                "--json windows",
                "--json inbox-scan 8 0",
            ],
            max_steps=3,
        ),
    ]

    results: List[Dict[str, Any]] = []
    for scenario in scenarios:
        results.append(evaluate_scenario(base_url, api_key, model, scenario))

    status_payload = run_skill_command("--json status")
    open_attempt: Dict[str, Any] = {
        "name": "session_flow",
        "goal": "Attempt a full session open/fetch/reply flow only if discovery succeeded.",
        "verdict": "blocked",
        "reason": "Skipped because there was no discoverable KakaoTalk window/room in the prerequisite checks.",
        "transcript": [{"status": status_payload}],
    }

    status_json = status_payload.get("json") or {}
    if status_json.get("connected"):
        scan_payload = run_skill_command("--json inbox-scan 8 0")
        scan_json = scan_payload.get("json") or {}
        rooms = scan_json.get("rooms") or scan_json.get("candidates") or []
        target = None
        if rooms:
            first = rooms[0]
            target = first.get("name") or first.get("room_name")
        if target:
            open_payload = run_skill_command(f'--json session-open "{target}"')
            open_json = open_payload.get("json") or {}
            transcript = [{"scan": scan_payload}, {"open": open_payload}]
            if open_json.get("ok"):
                session_id = open_json.get("session_id")
                fetch_payload = run_skill_command(f"--json session-fetch {session_id} latest 10")
                transcript.append({"fetch": fetch_payload})
                stream_payload = run_stream_command(f"event-watch {session_id} 2 3 6")
                transcript.append({"event_watch": stream_payload})
                close_payload = run_skill_command(f"--json session-close {session_id}")
                transcript.append({"close": close_payload})
                open_attempt = {
                    "name": "session_flow",
                    "goal": "Attempt a full session open/fetch/reply flow only if discovery succeeded.",
                    "verdict": "pass",
                    "reason": "Session open/fetch/event-watch/close path executed.",
                    "transcript": transcript,
                }
            else:
                open_attempt = {
                    "name": "session_flow",
                    "goal": "Attempt a full session open/fetch/reply flow only if discovery succeeded.",
                    "verdict": "partial",
                    "reason": "Discovery produced a target room but session-open did not succeed.",
                    "transcript": transcript,
                }
    results.append(open_attempt)

    daemon_payload = run_stream_command("daemon-run 3 5 3 6")
    results.append(
        {
            "name": "daemon_stream",
            "goal": "Verify the long-running daemon emits NDJSON events.",
            "verdict": "pass" if daemon_payload["events"] else "partial",
            "reason": "Observed daemon stream output." if daemon_payload["events"] else "Daemon produced no observable output in the sampling window.",
            "transcript": [{"daemon": daemon_payload}],
        }
    )

    report = {
        "ok": True,
        "runner": str(RUNNER),
        "model": model,
        "base_url": base_url,
        "results": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
