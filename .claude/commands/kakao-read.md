---
description: 현재 열린 KakaoTalk 채팅방의 메시지를 읽습니다. "카톡 메시지", "채팅 내용", "kakao read" 시 사용.
---

# Read KakaoTalk Messages

Read messages from the currently open chat room.

## Prerequisites

- A room must be open first
- Use `/kakao-open <n>` to open a room

## Read Messages

```bash
cd /Users/taehoje/space/kakao-terminal && python kakao_cli.py read $ARGUMENTS
```

### Options
- `/kakao-read` - Read last 20 messages
- `/kakao-read 50` - Read last 50 messages

## Output Format

```
=== Friend Name ===

[3:32 PM] Friend: Hello!
[3:33 PM] Me: Hi there
[3:35 PM] Friend: How are you?

--- January 27, 2026 ---

[9:00 AM] Friend: Good morning
[9:01 AM] Me: [Image]
```

## Notes

- Messages are read from the KakaoTalk window via Accessibility API
- The chat window must be open (even if in background)
- If no messages appear, the room may have closed

## Next Steps

- `/kakao-send "message"` - Reply to the conversation
- `/kakao-open <n>` - Switch to another room
- `/kakao-list` - View room list
