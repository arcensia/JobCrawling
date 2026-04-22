# 채용공고 일일 수집 봇 — 설계서 v2

작성일: 2026-04-20
대상: Leo (zxcklwe@gmail.com)

---

## 0. 요구사항 요약

- **직군**: 백엔드 / 풀스택 개발자 (Python, Java, Node.js, Spring 등)
- **경력**: 주니어 (1~3년)
- **지역**: 서울 / 수도권 (경기, 인천)
- **사이트**: 원티드, 사람인, 잡코리아 (LinkedIn 제외)
- **실행 주기**: 매일 아침 8시
- **전달 방식**: 이메일(Gmail SMTP) — 마크다운 요약본을 HTML로 렌더링
- **실행 환경**: AWS EC2 프리티어 + cron (최종), 로컬 PC (개발/테스트)

---

## 1. 실행 환경과 트리거

최종 배포 타겟은 AWS EC2 프리티어 (t2.micro 또는 t3.micro, Ubuntu 22.04 가정).
트리거는 리눅스 `cron` 사용.

```
0 8 * * * /home/ubuntu/job-bot/run.sh >> /home/ubuntu/job-bot/logs/cron.log 2>&1
```

매일 아침 8시(서버 로컬 시간 KST)에 스크립트가 자동 실행된다.
Cowork 스케줄 작업은 사용하지 않는다.

배포 전 로컬 PC 테스트 시에도 동일하게 cron(또는 Windows 작업 스케줄러)으로 돌려볼 수 있다.

---

## 2. 프로젝트 구조

```
job-bot/
├── run.sh                  # cron 래퍼 (venv 활성화 + main.py 실행)
├── main.py                 # 엔트리 포인트
├── collectors/
│   ├── __init__.py
│   ├── wanted.py           # 원티드 수집기
│   ├── saramin.py          # 사람인 수집기
│   └── jobkorea.py         # 잡코리아 수집기
├── core/
│   ├── filter.py           # 키워드/지역/경력 필터 + 중복 제거
│   ├── state.py            # 이미 본 공고 ID 저장
│   └── models.py           # Job 데이터 클래스
├── report/
│   └── markdown.py         # 마크다운 이메일 본문 생성
├── mailer/
│   └── smtp_sender.py      # Gmail SMTP 발송
├── config.yaml             # 키워드·지역·경력 설정
├── .env                    # SMTP 인증 정보 (git ignore)
├── .env.example            # 템플릿
├── requirements.txt
├── logs/                   # 실행 로그 (30일 로테이션)
├── state/
│   └── seen_jobs.json      # 과거 발송 공고 ID 목록
└── deploy/
    ├── setup.sh            # EC2 초기 설정 스크립트
    └── crontab.example     # cron 예시 라인
```

---

## 3. 데이터 흐름

```
08:00 cron 트리거
  ↓
run.sh → venv 활성화 → python main.py
  ↓
config.yaml 로드 (키워드/지역/경력/제외어)
  ↓
collectors/ 순차 실행
  ├─ wanted.py    → 원티드 API (JSON)
  ├─ saramin.py   → 사람인 검색 페이지 (HTML 파싱)
  └─ jobkorea.py  → 잡코리아 검색 페이지 (HTML 파싱)
  ↓
core/filter.py
  ├─ 키워드 매칭
  ├─ 경력 범위 체크 (1~3년)
  ├─ 지역 필터 (서울/경기/인천/원격)
  ├─ 제외어 필터
  └─ 중복 제거 (회사명 + 직무명 기준)
  ↓
core/state.py → seen_jobs.json 비교
  ├─ 오늘의 "신규" 공고 분리
  └─ 기존 "유효" 공고 분리
  ↓
report/markdown.py → 마크다운 본문 생성
  ↓
mailer/smtp_sender.py
  ├─ 마크다운 → HTML 변환
  ├─ MIMEMultipart (text/plain + text/html)
  └─ Gmail SMTP 발송 → zxcklwe@gmail.com
  ↓
seen_jobs.json 업데이트 (신규 공고 ID 추가, 30일 초과 정리)
  ↓
logs/bot_YYYY-MM-DD.log 기록
```

---

## 4. 마크다운 이메일 형식

Gmail은 `text/markdown` MIME을 직접 렌더링하지 않는다.
따라서 **마크다운을 HTML로 변환해서** `text/html` 파트로 넣고, 원본 마크다운은 `text/plain` 폴백으로 동봉한다.
결과적으로 Gmail 웹/앱 양쪽에서 깔끔하게 렌더링된다.

### 예시 본문

```markdown
# 📬 오늘의 채용공고 (2026-04-20)
백엔드/풀스택 · 주니어(1~3년) · 서울·수도권 · 총 23건 (신규 8건)

## 🆕 오늘 새로 뜬 공고 (8건)

### [원티드] 토스페이먼츠 - 백엔드 엔지니어 (주니어)
- 위치: 서울 강남구
- 기술: Java, Spring Boot, MSA
- 링크: https://www.wanted.co.kr/wd/12345

### [사람인] 당근마켓 - Python 서버 개발자
- 위치: 서울 서초구
- 경력: 1~3년
- 링크: https://www.saramin.co.kr/...

...

## 📋 아직 유효한 공고 (15건)
- [원티드] 몰로코 - 백엔드 → https://...
- [사람인] 리디 - 서버 개발자 → https://...
...

---
조건: 백엔드/풀스택 · 1~3년 · 서울/수도권
변경은 config.yaml 수정 후 서버 재배포.
```

신규와 기존을 분리하는 이유: 매일 아침 "오늘 새로 뜬 것"만 빠르게 훑기 위함.
기존 목록을 유지하는 이유: 마감일 전 재지원 고려 시 유용.
(원하시면 "신규만 발송"으로 축소 가능)

---

## 5. 사이트별 수집 전략

### 원티드
- 엔드포인트: `https://www.wanted.co.kr/api/chaos/jobs/v4/jobs` (공개 JSON API)
- 파라미터:
  - `locations=seoul.all,gyeonggi.all,incheon.all`
  - `years=1-3`
  - `query=백엔드` (키워드별 반복)
  - `limit=20`
- 인증 불필요
- 응답: JSON, 파싱 간단

### 사람인
- URL: `https://www.saramin.co.kr/zf_user/search/recruit`
- 파라미터:
  - `loc_mcd=101000,102000,108000` (서울/경기/인천)
  - `exp_cd=1,2,3` (1~3년)
  - `searchword=백엔드`
- 방식: requests + BeautifulSoup HTML 파싱
- 셀렉터: `.item_recruit` → `.job_tit a`, `.corp_name a`, `.job_condition`, `.job_sector`

### 잡코리아
- URL: `https://www.jobkorea.co.kr/Search/`
- 파라미터:
  - `stext=백엔드`
  - `careerMin=1&careerMax=3`
  - `local=I000` (서울)
- 방식: requests + BeautifulSoup HTML 파싱
- 셀렉터: `li.list-post` → `a.title`, `a.name`, `.option`

### 공통 주의사항
- User-Agent 헤더는 실제 브라우저처럼 설정
- 키워드 사이 `time.sleep(1)`로 차단 회피
- 타임아웃 15초, 실패 시 해당 collector만 실패 처리 (전체 중단 X)
- HTML 구조 변경 시 해당 collector 파일만 수정하면 됨

---

## 6. 비밀 관리

SMTP 비밀번호는 `.env` 파일에 두고 `.gitignore`에 포함한다.
`python-dotenv`로 로드한다.

```
# .env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=본인Gmail@gmail.com
SMTP_PASS=앱비밀번호16자리
RECIPIENT=zxcklwe@gmail.com
```

### Gmail 앱 비밀번호 발급
1. Google 계정 2단계 인증 활성화
2. https://myaccount.google.com/apppasswords
3. 앱 이름 "job-bot" 지정 → 16자리 비밀번호 생성
4. 생성된 비밀번호를 `.env`의 `SMTP_PASS`에 복사

AWS 배포 시에도 동일한 `.env` 파일을 `scp`로 업로드.
보안 강화가 필요하면 추후 AWS Parameter Store / Secrets Manager로 전환 가능.

---

## 7. 상태 관리 (중복 발송 방지)

파일: `state/seen_jobs.json`

구조:
```json
{
  "wanted:12345": "2026-04-18",
  "wanted:12346": "2026-04-19",
  "saramin:48257032": "2026-04-20",
  "jobkorea:98765": "2026-04-20"
}
```

- Key: `{사이트}:{공고ID}` 조합 (고유 식별자)
- Value: 첫 발견 날짜
- 매일 실행 시 새로 수집한 공고와 대조해 신규/기존 분류
- 30일 이상 된 엔트리는 자동 정리
- 외부 DB 불필요, 로컬 JSON만 사용

---

## 8. 로깅과 에러 처리

### 로깅
- `logs/bot_YYYY-MM-DD.log`
- Python `logging.TimedRotatingFileHandler`로 30일치 자동 로테이션
- 레벨: INFO (수집 결과), WARNING (부분 실패), ERROR (전체 실패)

### 에러 처리 전략
- 각 collector를 try/except로 감싸 **독립 실패** 보장
  → 원티드가 실패해도 사람인/잡코리아는 정상 처리
- 전체 실패(네트워크 다운 등) 시 state에 에러 플래그 기록
  → 다음날 이메일 제목에 `[⚠️ 어제 실행 실패]` 자동 표기
- SMTP 실패 시 3회 재시도 (지수 백오프)

---

## 9. AWS EC2 배포 절차

`deploy/setup.sh` 작성 예정. EC2 인스턴스 SSH 접속 후 한 번만 실행.

```bash
#!/usr/bin/env bash
set -e

# (1) 시스템 패키지
sudo apt update
sudo apt install -y python3-pip python3-venv git

# (2) 타임존 한국으로
sudo timedatectl set-timezone Asia/Seoul

# (3) 프로젝트 가상환경
cd ~/job-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# (4) .env 템플릿 복사 (이후 nano로 편집)
cp .env.example .env
echo "→ nano .env 로 SMTP 정보를 채워주세요"

# (5) cron 등록
(crontab -l 2>/dev/null; echo "0 8 * * * cd /home/ubuntu/job-bot && ./run.sh >> logs/cron.log 2>&1") | crontab -

echo "✅ 설치 완료. 수동 테스트: ./run.sh"
```

### EC2 프리티어 예상 리소스
- 인스턴스: t2.micro (1 vCPU, 1GB RAM)
- 스토리지: 8~30GB gp2 EBS
- 네트워크: 아웃바운드 15GB/월 무료
- 비용: 프리티어 한도 내 **월 $0**

---

## 10. 지금 구현할 범위 vs 나중에 할 일

### 지금 (이 세션에서)
- `job-bot/` 폴더 전체를 `/mnt/job_crowling/` 아래 완성
- 위 디렉토리 구조 그대로
- `collectors/`, `core/`, `report/`, `mailer/` 모듈 모두 포함
- `requirements.txt`, `.env.example`, `deploy/setup.sh` 포함
- **실행 테스트는 Cowork 샌드박스에서 불가** (외부 네트워크 차단)
  → Leo님 Mac 또는 EC2에서 실제 동작

### 나중에 (별도 세션)
- EC2 인스턴스 생성 및 보안 그룹 설정
- SSH 키페어 발급
- 프로젝트 scp 업로드 + `setup.sh` 실행
- `.env` 채우기 + 수동 테스트 실행
- cron 등록 확인

---

## 11. 기존 파일 정리

이전 단계에서 만든 다음 파일들은 이 구조로 재구성하면서 처리:

- `job_bot.py` → `main.py`, `collectors/*.py`, `mailer/smtp_sender.py` 등으로 분리
- `config.json` → `config.yaml` + `.env`로 분리 (설정과 비밀 분리)
- `reports/` 폴더 → 이메일 전송만 하므로 제거
- `README.md` → 배포 절차 포함한 버전으로 재작성
- 발송한 마크다운 원본을 `sent/` 폴더에 아카이빙할지 여부는 옵션 (기본은 안 함)

---

## 12. 확정 필요 사항

구현 시작 전 다음 항목만 확인:

1. **신규/기존 공고 분리 발송**을 유지할지 ("오늘 신규만"으로 축소할지)
2. 발송한 마크다운 본문을 서버에 아카이빙할지 (기본: 안 함)
3. 이메일 제목 포맷 선호 (예: `[채용공고 Daily] 2026-04-20 · 신규 8건`)

---

*이 문서는 구현 시작 전 합의를 위한 설계서이며, 구현 과정에서 변경사항이 생기면 여기에 반영한다.*
