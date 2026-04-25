#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
프로젝트 전역 경로 정의 (Single Source of Truth)
"""
import os
from pathlib import Path

# 환경변수로 override 가능 (Docker, CI, 테스트 환경 대응)
PROJECT_ROOT: Path = Path(
    os.environ.get("JOBBOT_HOME", Path(__file__).resolve().parent.parent)
)

DATA_DIR      = PROJECT_ROOT / "data"
REPORTS_DIR   = PROJECT_ROOT / "reports"
RESUME_DIR    = PROJECT_ROOT / "resume"
LOGS_DIR      = PROJECT_ROOT / "logs"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"

CONFIG_PATH         = PROJECT_ROOT / "config.json"
CONFIG_EXAMPLE_PATH = PROJECT_ROOT / "config.example.json"

# 자주 쓰는 파일
POOL_PATH    = DATA_DIR / "jobs_pool.json"
CLOSED_PATH  = DATA_DIR / "closed_jobs.json"
HISTORY_PATH = DATA_DIR / "jobs_history.json"
APPLIED_PATH = DATA_DIR / "applied.json"


def ensure_dirs() -> None:
    """앱 시작 시 1회 호출 — 필요한 디렉토리 일괄 생성."""
    for d in (DATA_DIR, REPORTS_DIR, RESUME_DIR, LOGS_DIR, SNAPSHOTS_DIR):
        d.mkdir(parents=True, exist_ok=True)