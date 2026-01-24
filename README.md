# kakao-terminal

회사에서 카톡하고 싶은데 눈치 보일 때 쓰는 터미널 카카오톡 클라이언트.
옆에서 보면 그냥 터미널에서 코딩하는 것처럼 보인다.

카카오톡 창은 백그라운드에 숨겨두고, macOS Accessibility API로 메시지를 읽고 보낸다.
카톡 창이 뜨지 않으니까 들킬 일이 없다.

## 필요한 것

- macOS 12 (Monterey) 이상
- KakaoTalk for Mac (v26.1.1에서 테스트됨)
- Python 3.10+
- 터미널에 접근성 권한 (시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용)

영어/일본어 macOS에서도 동작한다. 카카오톡이 시스템 언어를 따르기 때문에
시간(AM/PM, 오전/오후, 午前/午後), 날짜, 윈도우 타이틀 모두 자동 대응.

## 설치 및 실행

```bash
git clone https://github.com/stpcoder/kakao-terminal.git && cd kakao-terminal
./setup.sh
source venv/bin/activate
python app.py
```

## 명령어

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

## 구조

```
app.py            TUI (Textual)
kakao_bridge.py   카카오톡 Accessibility API 브릿지
```

## 동작 원리

카카오톡의 AX 트리를 직접 읽어서 메시지를 가져온다.
방 열기랑 메시지 전송만 AppleScript를 쓰고, 나머지는 전부 AX API.
카카오톡 창을 포그라운드로 안 가져오니까 다른 작업하면서 써도 된다.
