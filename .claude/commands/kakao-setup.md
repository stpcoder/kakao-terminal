---
description: KakaoTalk 연동을 위한 전제조건을 확인합니다. "카톡 설정", "카카오톡 연결", "kakao setup" 시 사용.
---

# KakaoTalk Setup

Check prerequisites for KakaoTalk integration with Claude.

## Prerequisites

1. **KakaoTalk running** - KakaoTalk Mac app must be running and logged in
2. **Accessibility permission** - Terminal must have accessibility access
3. **Chats tab active** - KakaoTalk main window must show the Chats tab

## Run Check

```bash
cd /Users/taehoje/space/kakao-terminal && python kakao_cli.py setup
```

## Fixing Issues

### KakaoTalk not running
- Launch KakaoTalk from Applications or Dock
- Log in to your account

### Accessibility permission denied
1. Open **System Preferences > Privacy & Security > Accessibility**
2. Add your terminal app:
   - Terminal.app
   - iTerm2
   - VS Code Terminal
   - Claude Desktop (if using)
3. Toggle the permission ON
4. Restart the terminal app

### Chats tab not active
- Click the **Chats** tab in KakaoTalk (not Friends or More)
- The chat room list should be visible

## Next Steps

Once all checks pass:
- `/kakao-list` - View chat rooms
- `/kakao-open 1` - Open first room
