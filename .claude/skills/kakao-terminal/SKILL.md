---
name: kakao-terminal
description: Operate KakaoTalk on macOS from an AI agent or terminal without leaving your workflow. Use this for setup checks, room browsing, opening chats, reading recent messages, sending messages when the user explicitly asks, searching rooms, refreshing, checking status, and navigating older or newer messages.
user-invocable: true
allowed-tools: Bash
argument-hint: <doctor|setup|list|open|read|send|status|search|up|down|refresh|rooms-next|rooms-prev|back|windows> [args]
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

- `python3 .claude/skills/kakao-terminal/scripts/run.py list`
- `python3 .claude/skills/kakao-terminal/scripts/run.py open "Room Name"`
- `python3 .claude/skills/kakao-terminal/scripts/run.py read 30`
- `python3 .claude/skills/kakao-terminal/scripts/run.py send "hello"`

## Safety

- Only use `send` when the user explicitly asks to send a message.
- If setup fails, read `references/prereqs.md` and report the missing prerequisite instead of retrying blindly.
- This skill only works on macOS with KakaoTalk running and accessibility permission granted to the terminal app.
