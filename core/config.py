#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
앱 설정 — pydantic 모델 + config.json 로더
"""

import json
from typing import Dict, List

from pydantic import BaseModel

from core.path import CONFIG_PATH


class DiscordConfig(BaseModel):
    webhook_url: str = ""
    bot_token: str = ""
    channel_id: str = ""
    top_n: int = 10


class AppConfig(BaseModel):
    keywords: List[str]
    exclude_keywords: List[str] = []
    years_min: int = 0
    years_max: int = 0
    include_newbie: bool = False
    locations: List[str] = []
    sites: Dict[str, bool]
    max_per_site: int = 0
    discord: DiscordConfig = DiscordConfig()


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"config.json이 없습니다: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return AppConfig(**cfg)
