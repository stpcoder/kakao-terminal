# Prerequisites

The bundled `kakao-terminal` skill works only when all of the following are true:

- macOS 12 or newer
- KakaoTalk for Mac is installed and signed in
- The terminal app running the skill has Accessibility permission
- KakaoTalk is open with the Chats tab visible
- Python 3.10 or newer is available for the bundled virtualenv

## Accessibility permission

1. Open `System Settings > Privacy & Security > Accessibility`
2. Add the terminal app you are using, such as Terminal, iTerm, Claude, or VS Code
3. Re-run `python3 .claude/skills/kakao-terminal/scripts/run.py doctor`

This skill should be executed from a local macOS GUI session. SSH-only shells, headless sessions, or remote terminals without direct GUI Accessibility access are not supported.

## Common failures

- `KakaoTalk is not running`
  Start KakaoTalk and sign in.
- `Accessibility permission denied`
  Grant permission to the terminal app, then retry.
- `Cannot read chat list`
  Switch KakaoTalk to the Chats tab instead of Friends or More.
- `It works in one terminal but not another`
  Accessibility permission is attached to the local GUI host app. Grant permission to the exact terminal or editor app that is launching the skill.

## Recommended operating pattern

- Use `doctor` at the start of a session
- Use `--json inbox-scan` before opening a room
- Use `session-open` and `session-fetch` for agent workflows
- Use `session-reply` only after an explicit human approval step
- Use `session-close` when the task is complete
- Use `sessions-list` and `sessions-cleanup` when stale sessions remain from interrupted or older runs

## Responsibility

Use of this skill is at the user's own risk.

The author does not guarantee account safety or policy compliance and is not responsible for account restrictions, service blocks, message failures, data loss, or other consequences caused by automation through this project.
