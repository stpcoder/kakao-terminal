---
name: kakao-terminal
description: Operate KakaoTalk on macOS from an AI agent or terminal without leaving your workflow. Use this for setup checks, inbox scanning, room resolution, opening conversation sessions, structured message reads, reply watching, and sending messages when the user explicitly asks.
user-invocable: true
allowed-tools: Bash
argument-hint: [--json] <doctor|setup|list|open|read|send|status|search|up|down|refresh|rooms-next|rooms-prev|back|windows|inbox-scan|room-resolve|session-open|session-fetch|session-watch|session-reply|session-close> [args]
---

# kakao-terminal

Use the bundled launcher instead of repository-specific paths.

## Setup

1. If the skill has not been installed in this project yet, run:
   `bash .claude/skills/kakao-terminal/scripts/install.sh`
2. Before the first command in a session, run:
   `python3 .claude/skills/kakao-terminal/scripts/run.py doctor`

If the skill is installed globally instead of per-project, use the same commands under `~/.claude/skills/kakao-terminal/scripts/`.

## Command runner

Run every action through:

`python3 .claude/skills/kakao-terminal/scripts/run.py <command> [args]`

Examples:

- `python3 .claude/skills/kakao-terminal/scripts/run.py --json inbox-scan`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json room-resolve "Room Name"`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-open "Room Name"`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-fetch conv_0001 latest 20`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-watch conv_0001 60 3 5`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-reply conv_0001 "hello"`

## Agent harness workflow

For agentic use, prefer the structured session commands over the low-level human commands.

1. Run `python3 .claude/skills/kakao-terminal/scripts/run.py doctor`
2. Scan rooms with `python3 .claude/skills/kakao-terminal/scripts/run.py --json inbox-scan`
3. Resolve or open a target room with `room-resolve` or `session-open`
4. Read and paginate with `session-fetch`
5. Wait for deltas with `session-watch`
6. Only when the user explicitly asks, send through `session-reply`
7. Release the room with `session-close`

## Safety

- Only use `send` or `session-reply` when the user explicitly asks to send a message.
- If setup fails, read `references/prereqs.md` and report the missing prerequisite instead of retrying blindly.
- This skill only works on macOS with KakaoTalk running and accessibility permission granted to the terminal app.
- Use this skill at your own risk. The author is not responsible for account restrictions, policy violations, delivery failures, data loss, or other damage caused by its use.
