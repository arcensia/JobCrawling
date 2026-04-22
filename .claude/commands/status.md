구직 현황을 보여줍니다. `--send` 옵션을 붙이면 Discord 로 발송합니다.

다음 순서로 실행하세요:

**1단계 — 리액션 동기화 (봇 꺼져 있어도 최신화)**

```bash
python3 reaction_sync.py
```

**2단계 — 현황 출력**

터미널 요약:
```bash
python3 status.py
```

전체 목록 (지원한 것 전부):
```bash
python3 status.py --detail
```

Discord 발송:
```bash
python3 status.py --send
```

출력 내용:
- ✅ 지원한 공고 목록 (최근 5건, --detail 시 전체)
- 🎯 관심 표시한 공고 목록
- ❌ 패스한 공고 수
- 이번 주 지원/관심/패스 건수
- 미검토 공고 수 (아직 리액션 안 단 열린 공고)
