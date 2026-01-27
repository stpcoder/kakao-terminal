---
description: KakaoTalk 연결 상태를 확인합니다. "카톡 상태", "연결 확인", "kakao status" 시 사용.
---

# KakaoTalk Status

Check the current connection status and session information.

## Check Status

```bash
cd /Users/taehoje/space/kakao-terminal && python kakao_cli.py status
```

## Output Format

```
=== KakaoTalk Status ===

Current room: Friend Name
Messages sent this session: 5
Connection: ✓ Connected
```

## Status Indicators

- **Current room**: The room currently open (from state file)
- **Messages sent**: Number of messages sent this session
- **Connection**:
  - ✓ Connected - All systems working
  - ✗ Not running - KakaoTalk needs to be launched
  - ✗ Permission denied - Accessibility permission needed
  - ⚠️ Issue - Chat tab may not be selected

## State File

Session state is stored in `~/.kakao-terminal-state.json`:
```json
{
  "current_room": "Friend Name",
  "session_sends": 5,
  "last_room_index": 3
}
```

## Next Steps

If connection issues:
- `/kakao-setup` - Run full prerequisite check

If connected:
- `/kakao-list` - View rooms
- `/kakao-read` - Read current room
