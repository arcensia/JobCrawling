import re
from typing import Union

from domain.job import Job


_HIGH_CAREER_PATTERNS = [
    re.compile(r"([4-9]|1\d)\s*년\s*(?:차\s*)?(?:이상|\+|↑|~)"),
    re.compile(r"([4-9]|1\d)\s*[~\-]\s*\d+\s*년"),
    re.compile(r"([4-9]|1\d)\s*년\s*차(?!\s*(?:이하|미만))"),
    re.compile(r"경력\s*([4-9]|1\d)\s*년(?!\s*(?:이하|미만|\d))"),
    # 상한이 7년 이상인 범위 표기 (예: "3~8년", "0~10년", "1~20년", "3~100년")
    re.compile(r"\d\s*[~\-]\s*([7-9]|[1-9]\d+)\s*년"),
]


def _fields(job: Union[Job, dict], keys: list[str]) -> list[str]:
    if isinstance(job, dict):
        return [job.get(k, "") for k in keys]
    return [getattr(job, k, "") for k in keys]


def is_high_career(job: Union[Job, dict]) -> bool:
    text = " ".join(_fields(job, ["title", "location", "company", "tags", "experience"]))
    return any(p.search(text) for p in _HIGH_CAREER_PATTERNS)


def has_excluded_keyword(job: Union[Job, dict], exclude_keywords: list[str]) -> bool:
    text = " ".join(_fields(job, ["title", "location", "tags", "experience"])).lower()
    return any(ex.lower() in text for ex in exclude_keywords)


def is_candidate(job: Union[Job, dict], exclude_keywords: list[str] | None = None) -> bool:
    if is_high_career(job):
        return False
    if exclude_keywords and has_excluded_keyword(job, exclude_keywords):
        return False
    return True
