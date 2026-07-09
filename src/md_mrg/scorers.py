from __future__ import annotations

import re
from dataclasses import dataclass
from time import perf_counter

from rapidfuzz import fuzz

from common.llama_gateway import BridgeScoreRequest, GatewayError, LlamaBridgeScoreGateway

from .models import CandidateEdge, DecisionStatus, EdgeScore

_TOKEN_RE = re.compile(r"[a-zA-Z0-9/#-]+")
_DATE_OR_NUMBER_RE = re.compile(r"\b(?:\d{1,4}[-/]\d{1,2}[-/]\d{1,4}|\d+[\.,]\d{2}|\d{4,})\b")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def _jaccard(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 0.0
    union = left_set | right_set
    if not union:
        return 0.0
    return len(left_set & right_set) / len(union)


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
class HeuristicEdgeScorer(EdgeScorer):
    pre_score_threshold: float = 2.5

    def _score_candidate(self, candidate: CandidateEdge) -> EdgeScore:
        started = perf_counter()

        boundary_ratio = fuzz.partial_ratio(candidate.from_fragment.last_line, candidate.to_fragment.first_line) / 100.0
        boundary_tokens_left = _tokenize(" ".join(_tokenize(candidate.from_fragment.last_line)[-5:]))
        boundary_tokens_right = _tokenize(" ".join(_tokenize(candidate.to_fragment.first_line)[:5]))
        boundary_overlap = 10.0 * (0.7 * boundary_ratio + 0.3 * _jaccard(boundary_tokens_left, boundary_tokens_right))

        summary_ratio = fuzz.token_set_ratio(candidate.from_fragment.snippet, candidate.to_fragment.snippet) / 100.0
        summary_overlap = 10.0 * summary_ratio

        numeric_left = _DATE_OR_NUMBER_RE.findall(
            " ".join([candidate.from_fragment.last_line, candidate.from_fragment.snippet])
        )
        numeric_right = _DATE_OR_NUMBER_RE.findall(
            " ".join([candidate.to_fragment.first_line, candidate.to_fragment.snippet])
        )
        numeric_entity_match = 10.0 * _jaccard(numeric_left, numeric_right)

        layout_hint = 0.0
        left_prefix = candidate.from_fragment.image_file.split("-")[0].lower()
        right_prefix = candidate.to_fragment.image_file.split("-")[0].lower()
        if left_prefix and left_prefix == right_prefix:
            layout_hint += 0.5

        score = max(
            0.0,
            min(
                10.0,
                0.45 * boundary_overlap + 0.35 * summary_overlap + 0.20 * numeric_entity_match + layout_hint,
            ),
        )
        latency_ms = (perf_counter() - started) * 1000.0
        return EdgeScore(
            from_fragment_id=candidate.from_fragment_id,
            to_fragment_id=candidate.to_fragment_id,
            score_0_10=score,
            reason=(
                f"heuristic boundary={boundary_overlap:.2f} summary={summary_overlap:.2f} "
                f"entities={numeric_entity_match:.2f} layout={layout_hint:.2f}"
            ),
            scorer_type="heuristic",
            latency_ms=latency_ms,
            decision_status=_decision_from_score(score),
            heuristic_score=score,
        )

    def score_edges(self, candidates: tuple[CandidateEdge, ...]) -> tuple[EdgeScore, ...]:
        scored = [self._score_candidate(candidate) for candidate in candidates]
        return tuple(score for score in scored if score.score_0_10 >= self.pre_score_threshold)


@dataclass
class LlmEdgeScorer(EdgeScorer):
    endpoint_url: str
    model_name: str
    timeout_seconds: float
    max_retries: int

    def score_edges(self, candidates: tuple[CandidateEdge, ...]) -> tuple[EdgeScore, ...]:
        scored: list[EdgeScore] = []
        with LlamaBridgeScoreGateway(
            endpoint_url=self.endpoint_url,
            model_name=self.model_name,
            request_timeout_seconds=self.timeout_seconds,
            request_max_retries=self.max_retries,
        ) as gateway:
            for candidate in candidates:
                started = perf_counter()
                try:
                    response = gateway.send_bridge_score_request(
                        BridgeScoreRequest(
                            page_a_end=candidate.from_fragment.last_line,
                            page_a_summary=candidate.from_fragment.snippet,
                            page_b_start=candidate.to_fragment.first_line,
                            page_b_summary=candidate.to_fragment.snippet,
                        )
                    )
                    score = float(response.bridge_score)
                    reason = response.reason
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
