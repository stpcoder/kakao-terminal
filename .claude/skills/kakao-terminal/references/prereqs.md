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

## Common failures

- `KakaoTalk is not running`
  Start KakaoTalk and sign in.
- `Accessibility permission denied`
  Grant permission to the terminal app, then retry.
- `Cannot read chat list`
  Switch KakaoTalk to the Chats tab instead of Friends or More.
