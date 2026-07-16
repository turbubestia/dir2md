from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from common.gateway import GatewayError, LlamaLanguageGateway, TextRequest

from .models import CandidateEdge, DecisionStatus, EdgeScore


def _decision_from_score(score: float) -> DecisionStatus:
    if score >= 7.0:
        return "auto_merge"
    if score >= 5.0:
        return "review_required"
    return "reject"


class EdgeScorer:
    def score_edges(self, candidates: tuple[CandidateEdge, ...]) -> tuple[EdgeScore, ...]:
        raise NotImplementedError


@dataclass
class LlmEdgeScorer(EdgeScorer):
    endpoint_url: str
    model_name: str
    timeout_seconds: float
    max_retries: int
    system_prompt: str

    def score_edges(self, candidates: tuple[CandidateEdge, ...]) -> tuple[EdgeScore, ...]:
        scored: list[EdgeScore] = []
        with LlamaLanguageGateway(
            endpoint_url=self.endpoint_url,
            model_name=self.model_name,
        ) as gateway:
            for candidate in candidates:
                started = perf_counter()
                try:
                    response = gateway.send_text_request(
                        TextRequest(
                            system_prompt=self.system_prompt,
                            user_prompt=(
                                f"Page A end: {candidate.from_fragment.last_line}\n"
                                f"Page A summary: {candidate.from_fragment.snippet}\n"
                                f"Page B start: {candidate.to_fragment.first_line}\n"
                                f"Page B summary: {candidate.to_fragment.snippet}\n"
                                "Return a score between 0 and 10 and a reason."
                            )
                        )
                    )
                    score = 0 #float(response.bridge_score)
                    reason = "" #response.reason
                except GatewayError as exc:
                    score = 0.0
                    reason = f"llm_error:{exc.error_code}"
                latency_ms = (perf_counter() - started) * 1000.0
                scored.append(
                    EdgeScore(
                        from_fragment_id=candidate.from_fragment_id,
                        to_fragment_id=candidate.to_fragment_id,
                        score_0_10=score,
                        reason=reason,
                        scorer_type="llm",
                        latency_ms=latency_ms,
                        decision_status=_decision_from_score(score),
                        heuristic_score=None,
                    )
                )
        return tuple(scored)
