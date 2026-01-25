# Developer Documentation

kakao-terminal 유지보수 및 확장을 위한 기술 문서.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     app.py (TUI Layer)                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  KakaoTerminal (Textual App)                        │   │
│  │  - State: in_chat, in_room_list, current_room       │   │
│  │  - UI: RichLog, Input, CommandPalette               │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  kakao_bridge.py (KakaoTalk API Layer)              │   │
│  │  - AX API: Direct element access (fast)             │   │
│  │  - AppleScript: Room selection, message send        │   │
│  │  - CGEvent: Background key events                   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              KakaoTalk.app (macOS)                          │
│  - Accessibility API를 통한 UI 트리 접근                     │
│  - AppleScript로 UI 조작 (선택, 전송)                        │
│  - CGEventPostToPid로 키 이벤트 전송                         │
└─────────────────────────────────────────────────────────────┘
```

## KakaoTalk AX Tree Structure

카카오톡의 Accessibility 트리 구조. `Accessibility Inspector.app`으로 확인 가능.

### Main Window (채팅방 목록)

```
AXApplication "KakaoTalk"
└── AXWindow "카카오톡" (또는 "KakaoTalk")
    └── AXScrollArea (scroll area 1)
        └── AXTable
            └── AXRow (각 채팅방)
                └── AXCell
                    ├── AXStaticText (방 이름)
                    ├── AXStaticText (시간)
                    ├── AXStaticText (마지막 메시지)
                    ├── AXStaticText (읽지 않음 수) ← 오른쪽 30% 영역에 위치
                    └── AXImage (프로필 사진)
```

### Chat Window (채팅 창)

```
AXWindow "채팅방 이름"
├── AXScrollArea (scroll area 1) ← 메시지 영역
│   └── AXTable
│       └── AXRow (각 메시지)
│           └── AXCell
│               ├── AXTextArea (메시지 본문)
│               ├── AXStaticText (발신자 이름) ← 받은 메시지만
│               ├── AXStaticText (시간)
│               ├── AXStaticText (읽음 수)
│               ├── AXImage (프로필) ← 받은 메시지만
│               └── AXImage (이미지 메시지)
│
└── AXScrollArea (scroll area 2) ← 입력 영역
    └── AXTextArea (text area 1) ← 메시지 입력창
```

### is_me 판별 로직

보낸 메시지와 받은 메시지를 구분하는 핵심 로직:

```python
# kakao_bridge.py:797-825
# 방법 1: TextArea의 X 좌표로 판별 (기본)
#   - 보낸 메시지: 오른쪽 정렬 (x > threshold)
#   - 받은 메시지: 왼쪽 정렬 (x <= threshold)
#   - threshold = scroll_area.x + (scroll_area.width * 0.3)

ta_pos = self._ax_val(ta_elem, 'AXPosition')
ta_x, _ = self._ax_coord(ta_pos)
is_me = ta_x > threshold

# 방법 2: Fallback (X좌표가 0일 때)
#   - 받은 메시지: 발신자 이름 또는 프로필 이미지가 있음
#   - 보낸 메시지: 없음
is_me = not has_sender_or_profile
```

## kakao_bridge.py API Reference

### Data Classes

```python
@dataclass
class ChatRoom:
    name: str           # 채팅방 이름
    time: str           # 마지막 메시지 시간
    last_message: str   # 마지막 메시지 미리보기
    unread: int = 0     # 읽지 않음 수
    row_index: int = 0  # AXTable 내 row index (1-based)

@dataclass
class Message:
    sender: str         # 발신자 (is_me=True면 빈 문자열)
    text: str           # 메시지 내용
    time: str = ""      # 시간 (오후 3:32)
    is_me: bool = False # 내가 보낸 메시지인지
    read_count: int = 0 # 읽지 않음 수
    is_date: bool = False # 날짜 구분선인지
```

### Core Methods

| Method | 구현 방식 | 용도 |
|--------|----------|------|
| `get_chat_rooms(limit, offset)` | AX API | 채팅방 목록 가져오기 |
| `get_chat_messages(limit, retry, msg_offset)` | AX API | 메시지 목록 가져오기 |
| `open_room_by_index(row_index, room_name)` | AppleScript + CGEvent | row index로 방 열기 |
| `open_room_by_name(room_name)` | AppleScript + CGEvent | 이름으로 방 열기 |
| `send_message(message)` | AppleScript + CGEvent | 메시지 전송 |
| `search_rooms(query)` | AX API (client-side) | 채팅방 검색 |
| `scroll_to_bottom()` | AX API | 스크롤 맨 아래로 |
| `get_latest_messages_fast(count)` | AX API | 빠른 메시지 조회 (auto-refresh용) |

### Helper Methods

| Method | 용도 |
|--------|------|
| `_get_pid()` | KakaoTalk PID 가져오기 (캐시됨) |
| `_get_ax_app()` | AXUIElement 앱 객체 (캐시됨) |
| `_get_main_title()` | 메인 윈도우 타이틀 감지 (캐시됨) |
| `_ax_val(elem, attr)` | AX 속성값 가져오기 |
| `_ax_coord(ax_value)` | AXValueRef에서 (x,y) 또는 (w,h) 추출 |
| `_find_ax_scroll_and_table(window_name)` | 윈도우에서 ScrollArea와 Table 찾기 |
| `_strip_emoji(text)` | AppleScript 호환을 위해 이모지 제거 |
| `_is_time_string(text)` | 시간 문자열 판별 (다국어) |
| `_is_date_string(text)` | 날짜 구분선 판별 (다국어) |
| `_is_read_count(text)` | 읽음 수 판별 |
| `_send_key(key_code)` | CGEventPostToPid로 키 이벤트 전송 |
| `_run_applescript(script, timeout)` | AppleScript 실행 |

### Diagnostic Methods

에러 발생 시 사용자에게 구체적인 해결 방법을 제시하는 진단 메서드:

```python
def diagnose_no_rooms(self) -> str:
    """채팅방 목록이 비어있을 때 원인 진단"""
    # 체크 순서:
    # 1. KakaoTalk 실행 중?
    # 2. 접근성 권한 있음?
    # 3. 윈도우 열려있음?
    # 4. 메인 윈도우 있음?
    # 5. Chats 탭인지? (Friends/More 탭이면 안 됨)

def diagnose_no_messages(self) -> str:
    """메시지 목록이 비어있을 때 원인 진단"""
    # 체크: current_room 설정됨? 채팅 창 열림?

def diagnose_send_failure(self) -> str:
    """메시지 전송 실패 시 원인 진단"""
    # 체크: current_room 설정됨? 채팅 창 열림?
```

## app.py State Management

### App States

```python
class KakaoTerminal(App):
    # 상태 변수
    self.in_chat = False      # 채팅방 안에 있는지
    self.in_room_list = False # 방 목록 보고 있는지
    self.current_room = None  # 현재 열린 방 이름
    self.room_offset = 0      # 방 목록 페이지네이션 offset
    self.msg_offset = 0       # 메시지 스크롤 offset (0=최신)
    self.room_list = []       # 현재 표시 중인 방 목록
    self.messages = []        # 현재 표시 중인 메시지
    self._refreshing = False  # 중복 refresh 방지 guard
```

### State Transitions

```
[시작]
   │
   ▼
[in_room_list=True]  ◄─── /l, /b, 시작 시
   │
   │ /o <n>
   ▼
[in_chat=True]  ◄─── 방 열기 성공
   │
   │ /b
   └──────────────► [in_room_list=True]
```

### Commands

| 명령어 | 설명 | State 변경 |
|--------|------|-----------|
| `/l` | 방 목록 | in_room_list=True, in_chat=False |
| `/o <n>` | n번 방 열기 | in_chat=True, in_room_list=False |
| `/r` | 새로고침 | 없음 |
| `/u`, `↑` | 이전 (방/메시지) | offset 증가 |
| `/d`, `↓` | 다음 (방/메시지) | offset 감소 |
| `/b` | 뒤로 | in_chat=False, in_room_list=True |
| `/s <q>` | 검색 | room_list=검색결과 |
| `/c` | 화면 정리 | 없음 |
| `/q` | 종료 | - |

### Auto-Refresh

```python
# 5초마다 실행
async def _auto_refresh(self) -> None:
    if self.in_chat:
        await self._refresh_messages_silent()  # 새 메시지 확인
    elif self.in_room_list:
        await self._refresh_rooms_silent()     # unread 수 업데이트
```

## Locale Support

### 지원 언어

| 언어 | 메인 윈도우 | 탭 이름 | 시간 형식 | 날짜 형식 |
|------|------------|---------|----------|----------|
| 한국어 | 카카오톡 | 전체, 안읽음, 즐겨찾기, 채팅, 친구, 더보기, 채널 | 오전/오후 H:MM | YYYY년 M월 D일 요일 |
| English | KakaoTalk | All, Unread, Favorites, Chats, Friends, More, Channels | H:MM AM/PM, HH:MM | Weekday, Month D, YYYY |
| 日本語 | KakaoTalk | 全体, 未読, お気に入り, トーク, 友だち, その他, チャンネル | 午前/午後 H:MM | YYYY年M月D日 曜日 |

### 구현 위치

```python
# 메인 윈도우 이름 (kakao_bridge.py:40)
MAIN_WINDOW_NAMES = ("카카오톡", "KakaoTalk", "Kakao Talk")

# skip_names (kakao_bridge.py:348-354)
skip_names = {
    "전체", "안읽음", "즐겨찾기", "채팅", "친구", "더보기", "채널",
    "All", "Unread", "Favorites", "Chats", "Friends", "More", "Channels",
    ""
}

# 시간 판별 (kakao_bridge.py:540-560)
def _is_time_string(text: str) -> bool:
    if text.startswith("오전 ") or text.startswith("오후 "):  # Korean
        return True
    if text.startswith("午前") or text.startswith("午後"):   # Japanese
        return True
    if text.endswith(" AM") or text.endswith(" PM"):         # English
        return bool(re.match(r'^\d{1,2}:\d{2}\s*[AP]M$', text))
    if re.match(r'^\d{1,2}:\d{2}$', text):                   # 24h
        return True

# 날짜 판별 (kakao_bridge.py:563-583)
def _is_date_string(text: str) -> bool:
    if "년 " in text and "월 " in text and "일" in text:     # Korean
        return True
    if "年" in text and "月" in text and "日" in text:       # Japanese
        return True
    # English: month name + 4-digit year
    months = ("January", ..., "December")
    for m in months:
        if m in text and re.search(r'\d{4}', text):
            return True
```

## Error Handling Patterns

### 1. Try-Except Wrapper

app.py에서 모든 kakao_bridge 호출을 try-except로 감싸서 crash 방지:

```python
try:
    rooms = self.kakao.get_chat_rooms(limit=10, offset=0)
except Exception:
    rooms = []
```

### 2. Diagnostic Error Messages

빈 결과 반환 시 진단 메서드로 구체적인 에러 메시지 표시:

```python
if rooms:
    # 정상 처리
else:
    reason = self.kakao.diagnose_no_rooms()
    log.write(f"[red]✗[/] {reason}")
```

### 3. Retry with Delay

메시지 로딩 시 재시도 로직:

```python
def get_chat_messages(self, limit=20, retry=2, msg_offset=0):
    for attempt in range(retry + 1):
        # ... 로직 ...
        if messages:
            return messages
        if attempt < retry:
            time.sleep(0.2)  # 재시도 전 대기
    return []
```

## Known Limitations

### 1. AppleScript 이모지 문제

AppleScript에서 이모지가 포함된 문자열 처리 시 오류 발생.
해결: `_strip_emoji()`로 이모지 제거 후 전달.

### 2. 오프스크린 메시지

화면에 보이지 않는 메시지는 AX 좌표가 (0,0)으로 반환됨.
해결: fallback으로 발신자/프로필 유무로 is_me 판별.

### 3. 이미지 메시지

이미지 메시지는 TextArea가 없어서 별도 처리 필요.
현재: `[Image]` 플레이스홀더로 표시.

### 4. KakaoTalk 버전 의존성

v26.1.1에서 테스트됨. 향후 버전에서 AX 트리 구조가 변경되면 수정 필요.

### 5. 접근성 권한

터미널에 접근성 권한이 없으면 동작하지 않음.
설정: 시스템 환경설정 > 개인정보 보호 및 보안 > 손쉬운 사용

## Testing

```bash
# 브릿지 단독 테스트
python kakao_bridge.py

# TUI 앱 실행
python app.py
```

### 수동 테스트 체크리스트

- [ ] KakaoTalk 미실행 시 에러 메시지
- [ ] 접근성 권한 없을 때 에러 메시지
- [ ] 메인 윈도우 닫혀있을 때 에러 메시지
- [ ] Friends/More 탭일 때 에러 메시지
- [ ] 한국어/영어 시스템 언어에서 동작
- [ ] 채팅방 목록 페이지네이션 (↑/↓)
- [ ] 메시지 스크롤 (↑/↓)
- [ ] 메시지 전송 및 수신 확인
- [ ] 이미지 메시지 표시
- [ ] 날짜 구분선 표시

## Future Improvements

### 1. 새 메시지 알림

현재 auto-refresh는 조용히 동작함. 새 메시지 도착 시 알림 옵션:
- Terminal bell (`\a`)
- 헤더/푸터에 배지 표시
- 터미널 타이틀 변경

### 2. 멀티 룸 모니터링

현재 열린 방만 모니터링. 전체 방 unread 수 변화 감지 가능.

### 3. 메시지 검색

채팅 내 메시지 검색 기능.

### 4. 파일 전송

현재 텍스트만 전송 가능. 파일/이미지 전송은 추가 구현 필요.

## Dependencies

```
textual>=0.40.0    # TUI 프레임워크
pyobjc-framework-ApplicationServices  # AX API
pyobjc-framework-Quartz  # CGEvent
pyobjc-framework-Cocoa   # Foundation
```

## References

- [Apple Accessibility Programming Guide](https://developer.apple.com/library/archive/documentation/Accessibility/Conceptual/AccessibilityMacOSX/)
- [Textual Documentation](https://textual.textualize.io/)
- [pyobjc Documentation](https://pyobjc.readthedocs.io/)
