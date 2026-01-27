# kakao-terminal

터미널에서 카카오톡을 제어하는 도구. Claude Code Skills와 CLI를 제공한다.

**핵심 기능:**
- **Claude Code Skills (14개)**: 자연어로 카톡 제어 ("카톡 방 목록 보여줘")
- **CLI (14개 명령어)**: 터미널에서 직접 실행 (`python kakao_cli.py list`)
- **TUI**: 인터랙티브 터미널 UI (`python app.py`)

회사에서 카톡하고 싶은데 눈치 보일 때 사용. 카카오톡 창은 백그라운드에 숨겨두고, macOS Accessibility API로 메시지를 읽고 보낸다. 옆에서 보면 터미널에서 코딩하는 것처럼 보인다.

---

## Claude Code Skills (2026)

Claude Code에서 자연어로 카카오톡을 제어. 2026 Skills 형식 적용.

### 자연어 사용 예시

```
"카톡 방 목록 보여줘" → /kakao-list
"3번 방 열어줘" → /kakao-open 3
"메시지 읽어줘" → /kakao-read
"안녕하세요 보내줘" → /kakao-send 안녕하세요
```

### Skills 명령어 (14개)

| 명령 | 설명 | 자연어 트리거 |
|------|------|--------------|
| `/kakao-setup` | 전제조건 체크 | "카톡 설정", "권한 확인" |
| `/kakao-list` | 채팅방 목록 | "카톡 방 목록", "채팅방 보여줘" |
| `/kakao-open <n>` | 방 열기 | "3번 방 열어", "채팅방 들어가줘" |
| `/kakao-read` | 메시지 읽기 | "메시지 보여줘", "채팅 내용" |
| `/kakao-send <msg>` | 메시지 전송 [주의] | "안녕 보내줘", "메시지 전송" |
| `/kakao-status` | 상태 확인 | "카톡 상태", "연결 확인" |
| `/kakao-search <q>` | 방 검색 | "친구 검색", "채팅방 찾기" |
| `/kakao-up` | 이전 메시지 | "위로 스크롤", "이전 메시지" |
| `/kakao-down` | 최신 메시지 | "아래로", "최신 메시지" |
| `/kakao-refresh` | 새로고침 | "새로고침", "리프레시" |
| `/kakao-rooms-next` | 다음 10개 방 | "다음 방들", "더 보기" |
| `/kakao-rooms-prev` | 이전 10개 방 | "이전 방들" |
| `/kakao-back` | 방 목록으로 | "뒤로 가기", "방 목록" |
| `/kakao-windows` | 열린 창 목록 | "창 목록", "열린 창" |

**[주의] kakao-send**: `disable-model-invocation: true` 설정으로 Claude가 자동으로 메시지를 보낼 수 없음. 사용자가 직접 `/kakao-send`를 입력해야 함.

### Skills 파일 구조

```
.claude/skills/
├── kakao-list/SKILL.md
├── kakao-open/SKILL.md
├── kakao-read/SKILL.md
├── kakao-send/SKILL.md       ← disable-model-invocation: true
├── kakao-search/SKILL.md
├── kakao-up/SKILL.md
├── kakao-down/SKILL.md
├── kakao-refresh/SKILL.md
├── kakao-rooms-next/SKILL.md
├── kakao-rooms-prev/SKILL.md
├── kakao-back/SKILL.md
├── kakao-windows/SKILL.md
├── kakao-setup/SKILL.md
└── kakao-status/SKILL.md
```

### SKILL.md 형식 (2026)

```yaml
---
name: kakao-send
description: 카카오톡 메시지 전송. "카톡 보내줘", "메시지 전송" 시 사용.
user-invocable: true
disable-model-invocation: true   # Claude 자동 호출 방지
allowed-tools: Bash
argument-hint: <메시지>
---

# 본문 (실행할 bash 명령어 포함)
```

---

## CLI (14개 명령어)

Claude Code 없이 터미널에서 직접 실행.

### 기본 워크플로우

```bash
source venv/bin/activate

python kakao_cli.py setup          # 전제조건 체크
python kakao_cli.py list           # 방 목록
python kakao_cli.py open 3         # 3번 방 열기
python kakao_cli.py read           # 메시지 읽기
python kakao_cli.py send "안녕"    # 메시지 전송
```

### 전체 명령어

```bash
# 기본
setup, list, open, read, send, status

# 네비게이션
search, up, down, refresh, rooms-next, rooms-prev, back, windows
```

### 출력 예시

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

`~/.kakao-terminal-state.json`:

```json
{
  "current_room": "친구이름",
  "session_sends": 5,
  "room_offset": 0,
  "msg_offset": 0,
  "in_chat": true
}
```

---

## TUI 모드

인터랙티브 터미널 UI:

```bash
python app.py
```

| 키 | 설명 |
|----|------|
| /l | 채팅방 목록 |
| /o n | n번 방 열기 |
| /s q | 방 검색 |
| /r | 새로고침 |
| /u /d | 스크롤 |
| /b | 뒤로 |
| /q | 종료 |

---

## 설치

```bash
git clone https://github.com/stpcoder/kakao-terminal.git
cd kakao-terminal
./setup.sh
source venv/bin/activate
```

### 요구사항

- macOS 12+ (Monterey)
- KakaoTalk Mac (v26.1.1 테스트됨)
- Python 3.10+
- 접근성 권한 (시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용)

### 언어 지원

한국어, English, 日本語 (시스템 언어 자동 감지)

---

## 경고

자동화된 메시지 전송은 카카오톡 이용약관 위반 가능성이 있으며, 계정 정지 위험이 있다.

**보호 장치:**
- Rate limiting: 500ms+ 딜레이
- 랜덤 지터: 100-300ms 추가
- 세션 추적: 50개 메시지 초과 시 경고
- Claude 자동 전송 방지: `disable-model-invocation: true`

---

## 프로젝트 구조

```
kakao_bridge.py   카카오톡 Accessibility API 브릿지
kakao_cli.py      CLI (14개 명령어)
app.py            TUI (Textual)
.claude/skills/   Claude Code Skills (14개)
```

## 동작 원리

카카오톡의 AX 트리를 직접 읽어서 메시지를 가져온다. 방 열기와 메시지 전송만 AppleScript를 사용하고, 나머지는 전부 AX API. 카카오톡 창을 포그라운드로 가져오지 않아서 다른 작업하면서 사용 가능.
