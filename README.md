# kakao-terminal

회사에서 카톡하고 싶은데 눈치 보일 때 쓰는 터미널 카카오톡 클라이언트.
옆에서 보면 그냥 터미널에서 코딩하는 것처럼 보인다.

카카오톡 창은 백그라운드에 숨겨두고, macOS Accessibility API로 메시지를 읽고 보낸다.
카톡 창이 뜨지 않으니까 들킬 일이 없다.

## 호환성

| 항목 | 지원 범위 |
|------|-----------|
| macOS | 12 (Monterey) 이상 |
| KakaoTalk | v26.1.1에서 테스트됨 |
| Python | 3.10+ |
| 시스템 언어 | 한국어, English, 日本語 |

카카오톡 Mac은 자체 언어 설정 없이 시스템 언어를 따른다.
시간(오전/오후, AM/PM, 午前/午後), 날짜, 윈도우 타이틀, 탭 이름 전부 자동 대응.

## 필요한 것

- 터미널에 접근성 권한 (시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용)
- KakaoTalk 실행 및 로그인 상태

## 설치 및 실행

```bash
git clone https://github.com/stpcoder/kakao-terminal.git && cd kakao-terminal
./setup.sh
source venv/bin/activate
python app.py
```

## 명령어 (TUI 모드)

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

## Claude Code 통합

Claude Code에서 카카오톡을 제어할 수 있다. `.claude/commands/` 폴더에 Skill 파일들이 있다.

### 사전 조건

1. **kakao-terminal 설치** - 위 설치 과정 완료
2. **접근성 권한** - Claude Code를 실행하는 터미널에 권한 부여
3. **KakaoTalk 실행** - 채팅 탭이 열려 있어야 함

### 워크플로우

```
/kakao-setup → /kakao-list → /kakao-open 3 → /kakao-read or /kakao-send
```

### Claude Code 명령어

| 명령 | 설명 |
|------|------|
| `/kakao-setup` | 전제조건 체크 (권한, 카톡 상태) |
| `/kakao-list` | 채팅방 목록 조회 |
| `/kakao-open <n>` | n번 채팅방 열기 |
| `/kakao-read` | 현재 방 메시지 읽기 |
| `/kakao-send <msg>` | 메시지 전송 |
| `/kakao-status` | 연결 상태 확인 |

### 자연어 호출

Claude에게 자연어로 요청하면 자동으로 해당 명령이 실행된다:

- "카톡 방 목록 보여줘" → `/kakao-list`
- "3번 방 열어" → `/kakao-open 3`
- "메시지 읽어줘" → `/kakao-read`
- "안녕하세요 보내줘" → `/kakao-send 안녕하세요`

### 상태 파일

세션 상태는 `~/.kakao-terminal-state.json`에 저장된다:

```json
{
  "current_room": "친구이름",
  "session_sends": 5,
  "last_room_index": 3
}
```

### CLI 직접 사용

Claude Code 없이 CLI로도 사용 가능:

```bash
python kakao_cli.py setup
python kakao_cli.py list
python kakao_cli.py open 3
python kakao_cli.py read
python kakao_cli.py send "안녕하세요"
python kakao_cli.py status
```

---

## 경고

자동화된 메시지 전송은 카카오톡 이용약관 위반 가능성이 있으며, 계정 정지 위험이 있다. 개인 용도로만 사용하고, 과도한 자동화는 피해야 한다.

보호 장치:
- Rate limiting: 메시지 전송 간 500ms+ 딜레이
- 랜덤 지터: 100-300ms 추가 딜레이
- 세션 추적: 50개 메시지 초과 시 경고

---

## 구조

```
app.py            TUI (Textual)
kakao_bridge.py   카카오톡 Accessibility API 브릿지
kakao_cli.py      Claude Code용 CLI 래퍼
.claude/commands/ Claude Code Skill 파일
```

## 동작 원리

카카오톡의 AX 트리를 직접 읽어서 메시지를 가져온다.
방 열기랑 메시지 전송만 AppleScript를 쓰고, 나머지는 전부 AX API.
카카오톡 창을 포그라운드로 안 가져오니까 다른 작업하면서 써도 된다.
