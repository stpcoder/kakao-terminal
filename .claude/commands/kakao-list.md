---
description: KakaoTalk 채팅방 목록을 조회합니다. "카톡 방 목록", "채팅방 확인", "kakao list" 시 사용.
---

# KakaoTalk Chat Rooms

List available chat rooms from KakaoTalk.

## Prerequisites

- KakaoTalk running and logged in
- Accessibility permission granted
- Chats tab selected in KakaoTalk

If you see errors, run `/kakao-setup` first.

## List Rooms

```bash
cd /Users/taehoje/space/kakao-terminal && python kakao_cli.py list
```

### With pagination

```bash
cd /Users/taehoje/space/kakao-terminal && python kakao_cli.py list 10 0   # First 10 rooms
cd /Users/taehoje/space/kakao-terminal && python kakao_cli.py list 10 10  # Rooms 11-20
```

## Output Format

```
=== Chat Rooms (1-10) ===

1. Friend Name (2 unread) - Last message preview...
2. Group Chat - See you tomorrow
3. Another Friend
...
```

## Next Steps

- `/kakao-open 3` - Open room #3
- `/kakao-open "Friend Name"` - Open room by name
