#!/bin/bash
# KakaoTalk Terminal 설치 스크립트

echo "=== KakaoTalk Terminal 설치 ==="
echo ""

# 가상환경 생성
if [ ! -d "venv" ]; then
    echo "📦 가상환경 생성 중..."
    python3 -m venv venv
fi

# 가상환경 활성화
source venv/bin/activate

# 의존성 설치
echo "📦 의존성 설치 중..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "✅ 설치 완료!"
echo ""
echo "실행 방법:"
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""
echo "⚠️  중요: 접근성 권한 필요"
echo "   → 시스템 환경설정 > 개인정보 보호 및 보안 > 손쉬운 사용"
echo "   → 터미널 앱 추가"
