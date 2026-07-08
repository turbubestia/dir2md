from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .io import flatten_loose_fragments, load_metadata_documents, split_documents_by_sequence, write_plan_file
from .models import CandidateEdge, EdgeScore, FragmentRecord, PlanConfig
from .scorers import HeuristicEdgeScorer, LlmEdgeScorer


@dataclass(frozen=True)
class PlanResult:
    output_path: Path
    document_count: int


def _build_candidate_edges(fragments: tuple[FragmentRecord, ...], rolling_window: int) -> tuple[CandidateEdge, ...]:
    edges: list[CandidateEdge] = []
    for index, fragment in enumerate(fragments):
        lower = max(0, index - rolling_window)
        upper = min(len(fragments), index + rolling_window + 1)
        for candidate_index in range(lower, upper):
            if candidate_index == index:
                continue
            target = fragments[candidate_index]
            edges.append(
                CandidateEdge(
                    from_fragment_id=fragment.fragment_id,
                    to_fragment_id=target.fragment_id,
                    from_fragment=fragment,
                    to_fragment=target,
                )
            )
    return tuple(edges)


def _creates_cycle(next_map: dict[str, str], start_id: str, target_id: str) -> bool:
    current = target_id
    while current in next_map:
        current = next_map[current]
        if current == start_id:
            return True
    return False


def _resolve_edges(scores: tuple[EdgeScore, ...]) -> tuple[EdgeScore, ...]:
    eligible = [score for score in scores if score.decision_status in {"auto_merge", "review_required"}]
    eligible.sort(
        key=lambda score: (
            -score.score_0_10,
            -(score.heuristic_score if score.heuristic_score is not None else -1.0),
            score.from_fragment_id,
            score.to_fragment_id,
        )
    )

    next_map: dict[str, str] = {}
    prev_map: dict[str, str] = {}
    accepted: list[EdgeScore] = []
    for score in eligible:
        from_id = score.from_fragment_id
        to_id = score.to_fragment_id
        if from_id in next_map or to_id in prev_map:
            continue
        if _creates_cycle(next_map, from_id, to_id):
            continue
        next_map[from_id] = to_id
        prev_map[to_id] = from_id
        accepted.append(score)
    return tuple(accepted)


def _build_documents_from_edges(
    fragments: tuple[FragmentRecord, ...],
    accepted_edges: tuple[EdgeScore, ...],
) -> tuple[dict[str, object], ...]:
    fragment_by_id = {fragment.fragment_id: fragment for fragment in fragments}
    next_map = {edge.from_fragment_id: edge.to_fragment_id for edge in accepted_edges}
    prev_map = {edge.to_fragment_id: edge.from_fragment_id for edge in accepted_edges}

    visited: set[str] = set()
    documents: list[dict[str, object]] = []

    for fragment in fragments:
        if fragment.fragment_id in prev_map:
            continue
        chain_ids: list[str] = []
        cursor = fragment.fragment_id
        while cursor not in visited and cursor in fragment_by_id:
            visited.add(cursor)
            chain_ids.append(cursor)
            if cursor not in next_map:
                break
            cursor = next_map[cursor]

        if not chain_ids:
            continue

        chain_fragments = [fragment_by_id[fragment_id] for fragment_id in chain_ids]
        related_edges = [
            edge
            for edge in accepted_edges
            if edge.from_fragment_id in chain_ids and edge.to_fragment_id in chain_ids
        ]
        review_required = any(edge.decision_status == "review_required" for edge in related_edges)
        average_score = (
            sum(edge.score_0_10 for edge in related_edges) / len(related_edges)
            if related_edges
            else 10.0
        )
        doc_id_source = "|".join(chain_ids)
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, doc_id_source))

        documents.append(
            {
                "document_id": document_id,
                "source_name": chain_fragments[0].source_name,
                "total_pages": len(chain_fragments),
                "is_verified_sequence": len(chain_fragments) > 1,
                "merge_confidence": round(average_score / 10.0, 4),
                "review_required": review_required,
                "source_document_ids": sorted({fragment.source_document_id for fragment in chain_fragments}),
                "fragments": [
                    {
                        "sequence_number": index + 1,
                        "image_file": chain_fragment.image_file,
                        "markdown_file": chain_fragment.markdown_file,
                        "anchors": {
                            "first_line": chain_fragment.first_line,
                            "last_line": chain_fragment.last_line,
                            "page_header": "",
                            "page_footer": "",
                        },
                        "content_fingerprint": {
                            "snippet": chain_fragment.snippet,
                            "detected_entities": [],
                        },
                    }
                    for index, chain_fragment in enumerate(chain_fragments)
                ],
            }
        )

    # Include any unvisited nodes as standalone documents.
    for fragment in fragments:
        if fragment.fragment_id in visited:
            continue
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, fragment.fragment_id))
        documents.append(
            {
                "document_id": document_id,
                "source_name": fragment.source_name,
                "total_pages": 1,
                "is_verified_sequence": False,
                "merge_confidence": 0.0,
                "review_required": True,
                "source_document_ids": [fragment.source_document_id],
                "fragments": [
                    {
                        "sequence_number": 1,
                        "image_file": fragment.image_file,
                        "markdown_file": fragment.markdown_file,
                        "anchors": {
                            "first_line": fragment.first_line,
                            "last_line": fragment.last_line,
                            "page_header": "",
                            "page_footer": "",
                        },
                        "content_fingerprint": {
                            "snippet": fragment.snippet,
                            "detected_entities": [],
                        },
                    }
                ],
            }
        )

    return tuple(documents)


def _score_candidates(config: PlanConfig, candidates: tuple[CandidateEdge, ...]) -> tuple[EdgeScore, ...]:
    if config.edge_scorer == "heuristic":
        return HeuristicEdgeScorer().score_edges(candidates)

    return LlmEdgeScorer(
        endpoint_url=config.llm_endpoint_url,
        model_name=config.llm_model_name,
        timeout_seconds=config.llm_timeout_seconds,
        max_retries=config.llm_max_retries,
    ).score_edges(candidates)


def build_merge_plan(config: PlanConfig) -> PlanResult:
    metadata_documents = load_metadata_documents(config.md_temp_dir)
    verified_documents, loose_documents = split_documents_by_sequence(metadata_documents)
    loose_fragments = flatten_loose_fragments(loose_documents)

    candidate_edges = _build_candidate_edges(loose_fragments, config.rolling_window)
    scored_edges = _score_candidates(config, candidate_edges)
    accepted_edges = _resolve_edges(scored_edges)

    planned_documents = [
        {
            **document,
            "merge_confidence": document.get("merge_confidence", 1.0),
            "review_required": bool(document.get("review_required", False)),
        }
        for document in verified_documents
    ]
    planned_documents.extend(_build_documents_from_edges(loose_fragments, accepted_edges))

    payload: dict[str, object] = {
        "schema_version": "2.0",
        "batch_id": str(uuid.uuid4()),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "md_temp_dir": str(config.md_temp_dir),
        "im_temp_dir": str(config.md_temp_dir.parent / "im-temp"),
        "scorer_mode": config.edge_scorer,
        "documents": planned_documents,
        "edge_scores": [
            {
                "from_fragment_id": score.from_fragment_id,
                "to_fragment_id": score.to_fragment_id,
                "score_0_10": round(score.score_0_10, 4),
                "reason": score.reason,
                "decision_status": score.decision_status,
                "scorer_type": score.scorer_type,
                "latency_ms": round(score.latency_ms, 4),
                "review_required": score.decision_status == "review_required",
            }
            for score in scored_edges
        ],
    }

    output_path = config.mg_temp_dir / "merge-plan.json"
    output_path = write_plan_file(output_path=output_path, payload=payload, overwrite=config.overwrite)
    return PlanResult(output_path=output_path, document_count=len(planned_documents))
