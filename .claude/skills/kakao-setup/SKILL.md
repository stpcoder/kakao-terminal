---
name: kakao-setup
description: 카카오톡 연동 전제조건 체크. "카톡 설정", "권한 확인", "kakao setup", "KakaoTalk setup" 시 사용.
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash
---

# 카카오톡 설정 체크

KakaoTalk 연동을 위한 전제조건을 확인합니다.

## 실행

```bash
cd /Users/taehoje/space/kakao-terminal && python kakao_cli.py setup
```

## 체크 항목

1. **카카오톡 실행 여부** - 앱이 실행되고 로그인되어 있어야 함
2. **접근성 권한** - 터미널에 권한이 부여되어 있어야 함
3. **창 열림 여부** - 카카오톡 창이 보여야 함
4. **채팅 탭 활성화** - 친구/더보기가 아닌 채팅 탭이어야 함

## 문제 해결

- 카카오톡 미실행 → Dock에서 실행 후 로그인
- 권한 거부 → 시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용
- 창 없음 → Dock에서 카카오톡 아이콘 클릭
- 탭 오류 → 카카오톡에서 "채팅" 탭 클릭

## 다음 단계

- `/kakao-list` - 채팅방 목록 보기
- `/kakao-status` - 연결 상태 확인
