#!/bin/bash
# cron 실행용 스크립트 (매일 아침 9 시)
# crontab 에 등록: 0 9 * * * /Users/kim-yeonghyeon/workplace/job_crowling/cron.sh >> /Users/kim-yeonghyeon/workplace/job_crowling/logs/cron.log 2>&1

cd /Users/kim-yeonghyeon/workplace/job_crowling
source venv/bin/activate
exec python3 job_bot_main.py >> logs/cron.log 2>&1
