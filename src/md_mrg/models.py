from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ScorerType = Literal["heuristic", "llm"]
DecisionStatus = Literal["auto_merge", "review_required", "reject"]


@dataclass(frozen=True)
class FragmentRecord:
    source_document_id: str
    source_name: str
    fragment_id: str
    sequence_number: int
    image_file: str
    markdown_file: str
    first_line: str
    last_line: str
    snippet: str


@dataclass(frozen=True)
class CandidateEdge:
    from_fragment_id: str
    to_fragment_id: str
    from_fragment: FragmentRecord
    to_fragment: FragmentRecord


@dataclass(frozen=True)
class EdgeScore:
    from_fragment_id: str
    to_fragment_id: str
    score_0_10: float
    reason: str
    scorer_type: ScorerType
    latency_ms: float
    decision_status: DecisionStatus
    heuristic_score: float | None = None


@dataclass(frozen=True)
class PlanConfig:
    md_temp_dir: Path
    mg_temp_dir: Path
    edge_scorer: ScorerType
    rolling_window: int
    llm_endpoint_url: str
    llm_model_name: str
    llm_timeout_seconds: float
    llm_max_retries: int
    overwrite: bool
