# kakao-terminal

회사에서 카톡하고 싶은데 눈치 보일 때 쓰는 터미널 카카오톡 클라이언트.
옆에서 보면 그냥 터미널에서 코딩하는 것처럼 보인다.

카카오톡 창은 백그라운드에 숨겨두고, macOS Accessibility API로 메시지를 읽고 보낸다.
카톡 창이 뜨지 않으니까 들킬 일이 없다.

---

## Claude Code Skills (2026)

Claude Code에서 자연어로 카카오톡을 제어할 수 있다. 2026 Skills 형식으로 구성.

### 빠른 시작

```
"카톡 방 목록 보여줘" → Claude가 /kakao-list 실행
"3번 방 열어줘" → /kakao-open 3
"메시지 읽어줘" → /kakao-read
"안녕하세요 보내줘" → /kakao-send 안녕하세요
```

### Claude Skills 명령어

| 명령 | 설명 | 자연어 예시 |
|------|------|------------|
| `/kakao-setup` | 전제조건 체크 | "카톡 설정 확인해줘" |
| `/kakao-list` | 채팅방 목록 | "카톡 방 목록" |
| `/kakao-open <n>` | 방 열기 | "3번 방 열어" |
| `/kakao-read` | 메시지 읽기 | "메시지 보여줘" |
| `/kakao-send <msg>` | 메시지 전송 ⚠️ | "안녕 보내줘" |
| `/kakao-status` | 상태 확인 | "카톡 상태" |
| `/kakao-search <q>` | 방 검색 | "친구 검색해줘" |
| `/kakao-up` | 이전 메시지 | "위로 스크롤" |
| `/kakao-down` | 최신 메시지 | "아래로" |
| `/kakao-refresh` | 새로고침 | "새로고침" |
| `/kakao-rooms-next` | 다음 10개 방 | "다음 방들" |
| `/kakao-rooms-prev` | 이전 10개 방 | "이전 방들" |
| `/kakao-back` | 방 목록으로 | "뒤로 가기" |
| `/kakao-windows` | 열린 창 목록 | "창 목록" |

⚠️ `/kakao-send`는 `disable-model-invocation: true`로 설정되어 Claude가 자동으로 메시지를 보낼 수 없음. 사용자가 직접 `/kakao-send`를 입력해야 함.

### Skills 구조 (2026 형식)

```
.claude/skills/
├── kakao-list/SKILL.md       # 방 목록
├── kakao-open/SKILL.md       # 방 열기
├── kakao-read/SKILL.md       # 메시지 읽기
├── kakao-send/SKILL.md       # 메시지 전송 (자동호출 불가)
├── kakao-search/SKILL.md     # 방 검색
├── kakao-up/SKILL.md         # 이전 메시지
├── kakao-down/SKILL.md       # 최신 메시지
├── kakao-refresh/SKILL.md    # 새로고침
├── kakao-rooms-next/SKILL.md # 다음 방 목록
├── kakao-rooms-prev/SKILL.md # 이전 방 목록
├── kakao-back/SKILL.md       # 뒤로가기
├── kakao-windows/SKILL.md    # 창 목록
├── kakao-setup/SKILL.md      # 설정 체크
└── kakao-status/SKILL.md     # 상태 확인
```

---

## CLI 직접 사용

Claude Code 없이 터미널에서 직접 사용 가능:

```bash
# 설치 후
source venv/bin/activate

# 기본 워크플로우
python kakao_cli.py setup          # 전제조건 체크
python kakao_cli.py list           # 방 목록
python kakao_cli.py open 3         # 3번 방 열기
python kakao_cli.py read           # 메시지 읽기 (안읽은 수, 시간 포함)
python kakao_cli.py send "안녕"    # 메시지 전송

# 네비게이션
python kakao_cli.py search "친구"  # 방 검색
python kakao_cli.py up             # 이전 메시지 (스크롤)
python kakao_cli.py down           # 최신 메시지
python kakao_cli.py refresh        # 새로고침
python kakao_cli.py rooms-next     # 다음 10개 방
python kakao_cli.py rooms-prev     # 이전 10개 방
python kakao_cli.py back           # 방 목록으로

# 상태 확인
python kakao_cli.py status         # 연결 상태
python kakao_cli.py windows        # 열린 창 목록
```

### CLI 출력 예시

```
=== 친구이름 ===

[오후 3:32] 친구: 안녕!
[오후 3:33] Me: 응 안녕 (1명 안읽음)
[오후 3:35] 친구: 뭐해?

--- 2026년 1월 27일 월요일 ---

[오후 4:00] 친구: 좋은 아침
[오후 4:01] Me: [Image] (3명 안읽음)
```

### 상태 파일

세션 상태는 `~/.kakao-terminal-state.json`에 저장:

```json
{
  "current_room": "친구이름",
  "session_sends": 5,
  "last_room_index": 3,
  "room_offset": 0,
  "msg_offset": 0,
  "in_chat": true
}
```

---

## TUI 모드

인터랙티브 터미널 UI로도 사용 가능:

```bash
source venv/bin/activate
python app.py
```

### TUI 명령어

| 키 | 설명 |
|----|------|
| /l | 채팅방 목록 |
| /o n | n번 방 열기 |
| /s q | 방 검색 |
| /r | 새로고침 |
| /u /d | 스크롤 |
| /b | 뒤로 |
| /c | 화면 정리 |
| /q | 종료 |

방에 들어가면 텍스트 입력 즉시 전송. 화살표 키로도 스크롤 가능.

---

## 설치

```bash
git clone https://github.com/stpcoder/kakao-terminal.git && cd kakao-terminal
./setup.sh
source venv/bin/activate
```

### 필요한 것

- macOS 12 (Monterey) 이상
- KakaoTalk Mac 앱 (v26.1.1에서 테스트됨)
- Python 3.10+
- 터미널에 접근성 권한 (시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용)

### 호환성

| 항목 | 지원 범위 |
|------|-----------|
| macOS | 12 (Monterey) 이상 |
| KakaoTalk | v26.1.1에서 테스트됨 |
| Python | 3.10+ |
| 시스템 언어 | 한국어, English, 日本語 |

카카오톡 Mac은 자체 언어 설정 없이 시스템 언어를 따른다.
시간(오전/오후, AM/PM, 午前/午後), 날짜, 윈도우 타이틀, 탭 이름 전부 자동 대응.

---

## 경고

자동화된 메시지 전송은 카카오톡 이용약관 위반 가능성이 있으며, 계정 정지 위험이 있다. 개인 용도로만 사용하고, 과도한 자동화는 피해야 한다.

**보호 장치:**
- Rate limiting: 메시지 전송 간 500ms+ 딜레이
- 랜덤 지터: 100-300ms 추가 딜레이
- 세션 추적: 50개 메시지 초과 시 경고
- Claude 자동 전송 방지: `disable-model-invocation: true`

---

## 구조

```
app.py            TUI (Textual)
kakao_bridge.py   카카오톡 Accessibility API 브릿지
kakao_cli.py      Claude Code용 CLI 래퍼 (14개 명령어)
.claude/skills/   Claude Code Skills (2026 형식, 14개)
```

## 동작 원리

카카오톡의 AX 트리를 직접 읽어서 메시지를 가져온다.
방 열기랑 메시지 전송만 AppleScript를 쓰고, 나머지는 전부 AX API.
카카오톡 창을 포그라운드로 안 가져오니까 다른 작업하면서 써도 된다.
