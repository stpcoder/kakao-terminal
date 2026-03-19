---
name: kakao-terminal
description: Operate KakaoTalk on macOS from an AI agent or terminal. Use this for setup checks, inbox scans, room resolution, conversation sessions, structured reads, safe replies, and long-running daemon or event-watch streams.
user-invocable: true
allowed-tools: Bash
argument-hint: [--json] <doctor|inbox-scan|room-resolve|session-open|session-fetch|session-reply|event-watch|daemon-run> [args]
---

# kakao-terminal

Use the bundled launcher instead of repository-specific paths.

## Quick Start

1. If the skill has not been installed in this project yet, run:
   `bash .claude/skills/kakao-terminal/scripts/install.sh`
2. Before the first command in a session, run:
   `python3 .claude/skills/kakao-terminal/scripts/run.py doctor`
3. For normal agent use, start with:
   `python3 .claude/skills/kakao-terminal/scripts/run.py --json inbox-scan`

If the skill is installed globally instead of per-project, use the same commands under `~/.claude/skills/kakao-terminal/scripts/`.

## Core Commands

Run every action through:

`python3 .claude/skills/kakao-terminal/scripts/run.py <command> [args]`

Examples:

- `python3 .claude/skills/kakao-terminal/scripts/run.py --json inbox-scan`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json room-resolve "Room Name"`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-open "Room Name"`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-fetch conv_0001 latest 20`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-reply conv_0001 "hello"`
- `python3 .claude/skills/kakao-terminal/scripts/run.py event-watch conv_0001 3 5 30`
- `python3 .claude/skills/kakao-terminal/scripts/run.py daemon-run 5 10 5 30`

## Agent harness workflow

Prefer the structured session commands over the low-level human commands.

1. Run `python3 .claude/skills/kakao-terminal/scripts/run.py doctor`
2. Scan rooms with `python3 .claude/skills/kakao-terminal/scripts/run.py --json inbox-scan`
3. Resolve or open a target room with `room-resolve` or `session-open`
4. Read and paginate with `session-fetch`
5. Only when the user explicitly asks, send through `session-reply`
6. For long-lived automation, use `event-watch` or `daemon-run`

Low-level commands such as `list`, `open`, `read`, `send`, `search`, and `back` still exist, but they are secondary. Use them only when debugging or when the high-level session commands are not enough.

## Safety

- Only use `send` or `session-reply` when the user explicitly asks to send a message.
- `event-watch` and `daemon-run` are streaming commands. Stop them explicitly when the monitoring task is complete.
- If setup fails, read `references/prereqs.md` and report the missing prerequisite instead of retrying blindly.
- This skill only works on macOS with KakaoTalk running and accessibility permission granted to the terminal app.
- Use this skill at your own risk. The author is not responsible for account restrictions, policy violations, delivery failures, data loss, or other damage caused by its use.
