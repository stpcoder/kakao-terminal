---
description: KakaoTalk 채팅방을 엽니다. "카톡방 열어줘", "채팅방 열기", "kakao open" 시 사용.
---

# Open KakaoTalk Chat Room

Open a chat room by number or name.

## Prerequisites

- KakaoTalk running with Chats tab visible
- Run `/kakao-list` first to see room numbers

## Open Room

The `$ARGUMENTS` variable contains the room number or name passed by the user.

### By number (recommended)
```bash
cd /Users/taehoje/space/kakao-terminal && python kakao_cli.py open $ARGUMENTS
```

If `$ARGUMENTS` is empty, prompt the user to provide a room number.

### Examples
- `/kakao-open 1` - Open first room
- `/kakao-open 3` - Open third room
- `/kakao-open "Friend Name"` - Open by name

## State Management

When a room is opened successfully:
- The room name is saved to `~/.kakao-terminal-state.json`
- Subsequent `/kakao-read` and `/kakao-send` will use this room

## Next Steps

After opening a room:
- `/kakao-read` - Read messages
- `/kakao-send "Hello"` - Send a message
- `/kakao-list` - Go back to room list
