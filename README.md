# JobBot - 채용공고 수집 봇

백엔드/풀스택 주니어 (1~3 년차) 채용공고를 수집하여 매일 이메일로 발송합니다.

## 특징

- **다중 사이트 수집**: 원티드, 사람인, 잡코리아
- **고도화된 필터링**: 키워드, 경력, 지역 필터링
- **자동화**: systemd 또는 cron 기반
- **리포팅**: HTML + Excel 리포트 생성
- **모니터링**: 실행 로그 및 상태 관리

## 빠른 시작 (AWS 서버)

### 1. 환경 설정

```bash
# Python 3.10+ 설치 (이미 있다면 생략)

# 필수 패키지 설치
pip install requests beautifulsoup4 openpyxl

# 실행 권한 설정
chmod +x test.sh systemd_service.sh cron.sh
```

### 2. 설정 파일 편집

`config.json` 파일을 편집하세요:

```json
{
  "email": {
    "enabled": true,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender": "your_email@gmail.com",
    "app_password": "YOUR_16_DIGIT_APP_PASSWORD",
    "recipient": "recipient@example.com"
  }
}
```

> **참고**: Gmail 앱 비밀번호는 [Google 계정에 액세스하기](https://myaccount.google.com/apppasswords) 에서 생성하세요.

### 3. systemd 자동화 설치 (권장)

```bash
sudo ./systemd_service.sh install
```

서비스 상태 확인:

```bash
sudo systemctl status job_bot
sudo journalctl -u job_bot -f
```

### 4. cron 자동화 (단순한 경우)

```bash
crontab -e
# 다음 줄 추가 (매일 아침 9 시):
0 9 * * * /Users/kim-yeonghyeon/workplace/job_crowling/cron.sh >> logs/cron.log 2>&1
```

### 5. 로컬 테스트

```bash
./test.sh
```

## 파일 구성

```
job_crowling/
├── job_bot_main.py       # 메인 봇 스크립트
├── config.json           # 설정 파일
├── requirements.txt      # Python 의존성
├── job_bot.service       # systemd 서비스 정의
├── systemd_service.sh    # 서비스 관리 스크립트
├── cron.sh              # cron 실행 스크립트
├── test.sh              # 로컬 테스트 스크립트
├── README.md            # 이 파일
├── reports/             # 생성된 리포트 (HTML, XLSX)
└── logs/                # 로그 파일
    ├── job_bot_YYYYMMDD.log
    └── status.json      # 실행 상태
```

## 수집 로직

- **키워드**: 백엔드, 서버, 풀스택, Python, Java, Node.js, Spring, FastAPI
- **경험**: 1~3 년차 (주니어)
- **지역**: 서울, 경기, 인천, 수도권, 원격
- **제외**: 시니어, 5 년 이상 필수, PHP 전문 등

## 이메일 발송

```python
# config.json 예시
{
  "email": {
    "enabled": true,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender": "bot@example.com",
    "app_password": "xxxx-xxxx-xxxx-xxxx",
    "recipient": "manager@example.com"
  }
}
```

## 사용법

```bash
python3 job_bot_main.py test    # 로컬 테스트
python3 job_bot_main.py status  # 실행 상태 조회
python3 job_bot_main.py version # 버전 정보
```

## AWS 배포 가이드

1. EC2 인스턴스 실행 (Ubuntu 22.04 권장)
2. Python 설치 및 패키지 설치
3. 코드 업로드 (SCP 또는 git clone)
4. `./systemd_service.sh install`
5. `sudo systemctl start job_bot`
6. 확인: `sudo systemctl status job_bot`

## 라이선스

MIT License
