#!/bin/bash
# 로컬 테스트 스크립트

echo "=== job_bot 로컬 테스트 ==="
echo "Python: $(python3 --version 2>&1)"
echo ""
echo "1. 필수 패키지 확인..."
python3 -m pip show requests beautifulsoup4 openpyxl | grep -E "^Name:|^Version:" || echo "미설치 패키지 있음"
echo ""
echo "2. config.json 확인..."
if [ -f "config.json" ]; then
    echo "✓ config.json 존재"
else
    echo "✗ config.json 없음 (생성됨)"
fi
echo ""
echo "3. 테스트 실행..."
echo ""
python3 job_bot_main.py test
