"""Claude 에이전트 랭커 + 실패 시 키워드 점수 fallback."""

from domain.ranking import keyword_score


class AgentWithFallbackRanker:
    def __init__(self, mode: str, applied_companies: list[str]):
        self._mode = mode
        self._applied = applied_companies

    def rank(self, jobs: list[dict], top_n: int) -> tuple[list[dict], list[dict]]:
        from agent_rank import agent_rank
        result = agent_rank(jobs, top_n, mode=self._mode, applied_companies=self._applied)
        if result:
            return result
        return keyword_score(jobs, top_n)
