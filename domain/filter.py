from domain.job import Job


def is_within_year_range(job: Job, min: int = -1, max: int = -1) ->bool:
    career_text = " ".join(
        job.title,
        job.location,
        job.company,
        job.tags
    )

    HIGH_CAREER_PATTERNS = [
        # "4년 이상", "4년+", "4년↑", "4년~", "4년차 이상"
        re.compile(r"([4-9]|1\d)\s*년\s*(?:차\s*)?(?:이상|\+|↑|~)"),
        # 범위 표기: "4~10년", "5-10년", "경력 5~7년"
        re.compile(r"([4-9]|1\d)\s*[~\-]\s*\d+\s*년"),
        # "4년차" 단독 (e.g., "4년차 백엔드"). "4년차 이하/미만"은 제외
        re.compile(r"([4-9]|1\d)\s*년\s*차(?!\s*(?:이하|미만))"),
        # "경력 4년" 평문 (이하/미만 제외)
        re.compile(r"경력\s*([4-9]|1\d)\s*년(?!\s*(?:이하|미만|\d))"),
    ]

    return any(p.search(text) for p in HIGH_CAREER_PATTERNS)

def has_excluded_keyword(job: Job, exclude_keywords: list[str]) ->bool:
    career_text = " ".join(
        job.title,
        job.location,
        job.tags,
        job.experience
    )

    for ex in exclude_keywords:
        if ex.lower() in career_text:
            return False
    return True

def is_candidate(job: Job) ->bool:
    ...