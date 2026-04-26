"""키워드 점수 기반 랭킹 — 도메인 규칙."""

PRIORITY_KEYWORDS = [
    "fastapi", "python", "kafka", "mongodb", "비동기",
    "백엔드", "docker", "k8s", "kubernetes",
    "java", "kotlin", "spring", "node.js", "go", "golang",
    "redis", "postgresql", "mysql", "aws", "gcp",
]


def _experience_score(job: dict) -> int:
    exp = job.get("experience", "")
    loc = job.get("location", "")
    title = job.get("title", "")
    full = f"{exp} {loc} {title}".lower()

    if "신입" in full:
        return 20
    if "경력3년" in full or "3년" in full:
        return 10
    if any(f"{y}년↑" in full or f"경력{y}년" in full for y in ["1", "2"]):
        return 30
    try:
        parts = exp.replace("년", "").split("~")
        ann_from = int(parts[0])
        ann_to = int(parts[1]) if len(parts) > 1 else 99
        if 1 <= ann_from <= 3 and ann_to <= 3:
            return 30
        if ann_from == 0:
            return 20
        if ann_from >= 3:
            return 10
    except (ValueError, IndexError):
        pass
    return 30


def _keyword_score(job: dict) -> int:
    text = job.get("title", "").lower()
    return sum(1 for kw in PRIORITY_KEYWORDS if kw in text)


def keyword_score(jobs: list[dict], top_n: int) -> tuple[list[dict], list[dict]]:
    """경력 적합도 + 키워드 일치 수로 정렬해 (top_n, 나머지)로 분리."""
    ranked = sorted(jobs, key=lambda j: (_experience_score(j), _keyword_score(j)), reverse=True)
    return ranked[:top_n], ranked[top_n:]
