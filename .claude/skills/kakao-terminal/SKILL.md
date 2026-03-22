---
name: kakao-terminal
description: Operate KakaoTalk on macOS from an AI agent or terminal. Use this for setup checks, inbox scans, room resolution, conversation sessions, structured reads, safe replies, lingering session cleanup, and long-running daemon or event-watch streams.
user-invocable: true
allowed-tools: Bash
argument-hint: [--json] <doctor|inbox-scan|room-resolve|session-open|session-fetch|session-reply|session-close|sessions-list|sessions-cleanup|event-watch|daemon-run> [args]
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

This skill is meant for a local macOS GUI terminal session. Do not assume SSH-only or headless execution will work.

## Core Commands

Run every action through:

`python3 .claude/skills/kakao-terminal/scripts/run.py <command> [args]`

Examples:

- `python3 .claude/skills/kakao-terminal/scripts/run.py --json inbox-scan`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json room-resolve "Room Name"`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-open "Room Name"`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-fetch conv_0001 latest 20`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-reply conv_0001 "hello"`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-close conv_0001`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json sessions-list 30`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json sessions-cleanup 30`
- `python3 .claude/skills/kakao-terminal/scripts/run.py event-watch conv_0001 3 5 30`
- `python3 .claude/skills/kakao-terminal/scripts/run.py daemon-run 5 10 5 30`

## Agent harness workflow

Prefer the structured session commands over the low-level human commands.

1. Run `python3 .claude/skills/kakao-terminal/scripts/run.py doctor`
2. Scan rooms with `python3 .claude/skills/kakao-terminal/scripts/run.py --json inbox-scan`
3. Resolve or open a target room with `room-resolve` or `session-open`
4. Read and paginate with `session-fetch`
5. If no send is needed, close with `session-close`
6. Only when the user explicitly asks and the final message text is approved, send through `session-reply`
7. After sending, close with `session-close`
8. For long-lived automation, use `event-watch` or `daemon-run`
9. If stale sessions remain from earlier interrupted runs, inspect with `sessions-list` and clear them with `sessions-cleanup`

Low-level commands such as `list`, `open`, `read`, `send`, `search`, and `back` still exist, but they are secondary. Use them only when debugging or when the high-level session commands are not enough.

## Reply approval boundary

There are two distinct modes:

- `draft/review mode`
  Read rooms, summarize, and prepare a candidate reply if needed. Do not call `session-reply`.
- `approved send mode`
  Only after the user explicitly approves the exact final message text should you call `session-reply`.

Recommended pattern:

1. `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-open "Room Name"`
2. `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-fetch conv_0001 latest 20`
3. Present a draft or explain that no reply is needed
4. Wait for explicit approval
5. `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-reply conv_0001 "Approved message text"`
6. `python3 .claude/skills/kakao-terminal/scripts/run.py --json session-close conv_0001`

If you are not certain whether a reply should be sent, stop in draft/review mode and ask the user.

## Stale sessions

Normal wrappers should close the sessions they open. If monitoring or old tests are still referencing previous sessions, use:

- `python3 .claude/skills/kakao-terminal/scripts/run.py --json sessions-list 30`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json sessions-cleanup 30`
- `python3 .claude/skills/kakao-terminal/scripts/run.py --json sessions-cleanup --force`

Use forced cleanup when an earlier run crashed, or when you need a clean monitoring baseline.

## Safety

- Only use `send` or `session-reply` when the user explicitly asks to send a message and has approved the exact final text.
- Prefer `session-open` / `session-fetch` / `session-close` over low-level room state when acting as an agent.
- `event-watch` and `daemon-run` are streaming commands. Stop them explicitly when the monitoring task is complete.
- If setup fails, read `references/prereqs.md` and report the missing prerequisite instead of retrying blindly.
- This skill only works on macOS with KakaoTalk running and accessibility permission granted to the terminal app.
- Use this skill at your own risk. The author is not responsible for account restrictions, policy violations, delivery failures, data loss, or other damage caused by its use.
