---
description: KakaoTalk으로 메시지를 전송합니다. "카톡 보내기", "메시지 전송", "kakao send" 시 사용.
user-invocable: true
---

# Send KakaoTalk Message

Send a message to the currently open chat room.

## Warning

Automated message sending may violate KakaoTalk's Terms of Service and could result in account suspension. Use responsibly for personal purposes only.

## Prerequisites

- A room must be open first
- Use `/kakao-open <n>` to open a room

## Send Message

```bash
cd /Users/taehoje/space/kakao-terminal && python kakao_cli.py send "$ARGUMENTS"
```

### Examples
- `/kakao-send Hello!`
- `/kakao-send "Meeting at 3pm tomorrow"`
- `/kakao-send 안녕하세요`

## Safety Features

- **Rate limiting**: 500ms+ delay between messages
- **Random jitter**: Additional 100-300ms random delay
- **Session tracking**: Warning after 50 messages
- **User-invocable only**: Claude should not auto-invoke this command

## Next Steps

- `/kakao-read` - Check for responses
- `/kakao-open <n>` - Switch rooms
- `/kakao-status` - Check session stats
