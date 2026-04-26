"""키워드 점수 랭커 — Ranker 포트 구현."""

from domain.ranking import keyword_score


class KeywordRanker:
    def rank(self, jobs: list[dict], top_n: int) -> tuple[list[dict], list[dict]]:
        return keyword_score(jobs, top_n)
