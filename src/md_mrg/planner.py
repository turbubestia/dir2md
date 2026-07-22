from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from common.config import AppConfig
from common.gateway import GatewayError, LlamaLanguageGateway, TextRequest

BATCH_FILE_NAME = "batch.json"
MERGE_PLAN_FILE_NAME = "batch_mrg.json"
SCORE_THRESHOLD = 5.0

PlanningProgressKind = Literal[
    "plan_start",
    "comparison_start",
    "comparison_complete",
    "plan_persisted",
    "complete",
    "failed",
]


@dataclass(frozen=True)
class PlanningProgressEvent:
    kind: PlanningProgressKind
    total_comparisons: int = 0
    completed_comparisons: int = 0
    left_source_id: str | None = None
    right_source_id: str | None = None
    left_display_name: str | None = None
    right_display_name: str | None = None
    score_status: str | None = None
    score: float | None = None
    pdf_document_count: int = 0
    image_group_count: int = 0
    error_code: str | None = None
    message: str | None = None


PlanningProgressCallback = Callable[[PlanningProgressEvent], None]


class PlannerError(RuntimeError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class ScoreOutcome:
    score: float | None
    error_code: str | None = None
    detail: str | None = None
    response_text: str | None = None


def _validate_plan_inputs(source_dir: Path | None, cfg: AppConfig) -> None:
    if source_dir is None:
        raise PlannerError("batch_file_not_found", "Input source directory is not configured")
    if not source_dir.exists() or not source_dir.is_dir():
        raise PlannerError("batch_file_not_found", f"Input source directory does not exist: {source_dir}")

    if cfg.language_model.endpoint_url is None:
        raise PlannerError("language_model_endpoint_not_specified", "Language model endpoint must be configured before planning starts")
    if cfg.language_model.model_name is None:
        raise PlannerError("language_model_name_not_specified", "Language model name must be configured before planning starts")
    if not cfg.md_mrg.score.system_text.strip():
        raise PlannerError("md_mrg_score_prompt_missing", "Merge scoring prompt must be configured before planning starts")


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PlannerError("batch_read_failed", f"Failed to read JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PlannerError("batch_invalid_json", f"Invalid JSON in file: {path}") from exc

    if not isinstance(payload, dict):
        raise PlannerError("batch_invalid_shape", f"Expected JSON object in file: {path}")
    return payload


def _validate_document_list(payload: dict[str, Any], file_label: str) -> list[dict[str, Any]]:
    documents = payload.get("documents", [])
    if documents is None:
        return []
    if not isinstance(documents, list):
        raise PlannerError("documents_invalid", f"'{file_label}.documents' must be a list")

    out: list[dict[str, Any]] = []
    for item in documents:
        if isinstance(item, dict):
            out.append(item)
    return out


def _load_markdown(source_dir: Path, document: dict[str, Any]) -> str:
    markdown_file = document.get("markdown_file")
    if not isinstance(markdown_file, str) or not markdown_file.strip():
        raise PlannerError("markdown_file_missing", "Document is missing markdown_file")

    markdown_path = source_dir / markdown_file
    try:
        return markdown_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PlannerError("markdown_read_failed", f"Failed to read markdown file: {markdown_path}") from exc


def _build_score_user_prompt(page_a_text: str, page_b_text: str) -> str:
    return (
        "# Page A content\n"
        "--- start of Page A content ---\n"
        f"{page_a_text}\n"
        "--- end of Page A content ---\n\n"
        "---\n\n"
        "# Page B content\n"
        "--- start of Page B content ---\n"
        f"{page_b_text}\n"
        "--- end of Page B content ---\n"
    )


def _parse_score_response(response_text: str) -> float:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise PlannerError("score_parse_failed", "Score response is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise PlannerError("score_parse_failed", "Score response must be a JSON object")

    score_key = "bridge_score" if "bridge_score" in payload else "score"
    score = payload.get(score_key)
    if not isinstance(score, (int, float)):
        raise PlannerError(
            "score_parse_failed",
            f"Score response must contain numeric '{score_key}'",
        )

    return float(score)


def _score_pair(
    source_dir: Path,
    gateway: LlamaLanguageGateway,
    score_prompt: str,
    page_a: dict[str, Any],
    page_b: dict[str, Any],
) -> ScoreOutcome:
    response_text: str | None = None
    try:
        page_a_text = _load_markdown(source_dir, page_a)
        page_b_text = _load_markdown(source_dir, page_b)

        request = TextRequest(
            system_prompt=score_prompt,
            user_prompt=_build_score_user_prompt(page_a_text=page_a_text, page_b_text=page_b_text),
            assistant_prompt="",
        )
        response = gateway.send_text_request(request)
        response_text = response.text
        score = _parse_score_response(response.text)
        return ScoreOutcome(score=score, response_text=response.text)
    except PlannerError as exc:
        return ScoreOutcome(
            score=None,
            error_code=exc.error_code,
            detail=str(exc),
            response_text=response_text,
        )
    except GatewayError as exc:
        return ScoreOutcome(score=None, error_code=exc.error_code, detail=str(exc))


def _partition_documents(documents: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    images: list[dict[str, Any]] = []
    pdfs: list[dict[str, Any]] = []

    for document in documents:
        if document.get("file_type") == "image":
            images.append(document)
        else:
            pdfs.append(document)

    return images, pdfs


def _as_group(documents: list[dict[str, Any]]) -> dict[str, Any]:
    return {"documents": documents}


def _emit_progress(
    progress_callback: PlanningProgressCallback | None,
    event: PlanningProgressEvent,
) -> None:
    if progress_callback is not None:
        progress_callback(event)


def _document_id(document: dict[str, Any]) -> str | None:
    source_file_name = document.get("source_file_name")
    if isinstance(source_file_name, str) and source_file_name:
        return source_file_name
    markdown_file = document.get("markdown_file")
    if isinstance(markdown_file, str) and markdown_file:
        return markdown_file
    return None


def _display_name(document: dict[str, Any]) -> str:
    return _document_id(document) or "<unknown>"


def _build_groups(
    source_dir: Path,
    gateway: LlamaLanguageGateway,
    score_prompt: str,
    image_documents: list[dict[str, Any]],
    *,
    progress_callback: PlanningProgressCallback | None = None,
    total_comparisons: int = 0,
    pdf_document_count: int = 0,
) -> list[dict[str, Any]]:
    if not image_documents:
        return []

    groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = [image_documents[0]]
    completed_comparisons = 0

    left_index = 0
    right_index = 1

    while right_index < len(image_documents):
        page_a = image_documents[left_index]
        page_b = image_documents[right_index]
        file_name_a = _display_name(page_a)
        file_name_b = _display_name(page_b)
        _emit_progress(
            progress_callback,
            PlanningProgressEvent(
                kind="comparison_start",
                total_comparisons=total_comparisons,
                completed_comparisons=completed_comparisons,
                left_source_id=_document_id(page_a),
                right_source_id=_document_id(page_b),
                left_display_name=file_name_a,
                right_display_name=file_name_b,
                pdf_document_count=pdf_document_count,
            ),
        )
        score_outcome = _score_pair(source_dir, gateway, score_prompt, page_a, page_b)
        completed_comparisons += 1
        _emit_progress(
            progress_callback,
            PlanningProgressEvent(
                kind="comparison_complete",
                total_comparisons=total_comparisons,
                completed_comparisons=completed_comparisons,
                left_source_id=_document_id(page_a),
                right_source_id=_document_id(page_b),
                left_display_name=file_name_a,
                right_display_name=file_name_b,
                score_status="failed" if score_outcome.score is None else "scored",
                score=score_outcome.score,
                pdf_document_count=pdf_document_count,
            ),
        )
        print(
            f"{file_name_a} <=> {file_name_b} == {score_outcome.score} "
            # f"response={score_outcome.response_text!r}"
        )

        if score_outcome.score is None or abs(score_outcome.score) < SCORE_THRESHOLD:
            groups.append(current_group)
            current_group = [page_b]
            left_index = right_index
            right_index = left_index + 1
            continue

        if score_outcome.score >= 0:
            if page_b not in current_group:
                current_group.append(page_b)
            left_index = right_index
            right_index = left_index + 1
            continue

        if page_b in current_group:
            current_group.remove(page_b)

        try:
            insertion_index = current_group.index(page_a)
        except ValueError:
            current_group.append(page_a)
            insertion_index = len(current_group) - 1
        current_group.insert(insertion_index, page_b)
        right_index += 1

    groups.append(current_group)
    return [_as_group(group) for group in groups]


def run_plan(
    source_dir: Path | None,
    cfg: AppConfig,
    *,
    progress_callback: PlanningProgressCallback | None = None,
) -> dict[str, Any]:
    try:
        _validate_plan_inputs(source_dir, cfg)

        assert source_dir is not None
        batch_path = source_dir / BATCH_FILE_NAME
        plan_path = source_dir / MERGE_PLAN_FILE_NAME

        if not batch_path.exists():
            raise PlannerError("batch_file_not_found", f"Input batch file does not exist: {batch_path}")

        payload = _read_json_file(batch_path)
        documents = _validate_document_list(payload, "batch")
        image_documents, pdf_documents = _partition_documents(documents)
        total_comparisons = max(len(image_documents) - 1, 0)
        pdf_document_count = len(pdf_documents)
        _emit_progress(
            progress_callback,
            PlanningProgressEvent(
                kind="plan_start",
                total_comparisons=total_comparisons,
                pdf_document_count=pdf_document_count,
            ),
        )

        with LlamaLanguageGateway(
            endpoint_url=cfg.language_model.endpoint_url,
            model_name=cfg.language_model.model_name,
        ) as gateway:
            gateway.request_timeout_seconds = cfg.language_model.request_timeout_seconds
            gateway.request_max_retries = cfg.language_model.request_max_retries
            groups = _build_groups(
                source_dir=source_dir,
                gateway=gateway,
                score_prompt=cfg.md_mrg.score.system_text,
                image_documents=image_documents,
                progress_callback=progress_callback,
                total_comparisons=total_comparisons,
                pdf_document_count=pdf_document_count,
            )

        image_group_count = len(groups)
        merged_documents: list[dict[str, Any]] = []
        merged_documents.extend(groups)
        merged_documents.extend(pdf_documents)

        output_payload = {"documents": merged_documents}
        plan_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _emit_progress(
            progress_callback,
            PlanningProgressEvent(
                kind="plan_persisted",
                total_comparisons=total_comparisons,
                completed_comparisons=total_comparisons,
                pdf_document_count=pdf_document_count,
                image_group_count=image_group_count,
            ),
        )
        _emit_progress(
            progress_callback,
            PlanningProgressEvent(
                kind="complete",
                total_comparisons=total_comparisons,
                completed_comparisons=total_comparisons,
                pdf_document_count=pdf_document_count,
                image_group_count=image_group_count,
            ),
        )

        return output_payload
    except PlannerError as exc:
        _emit_progress(
            progress_callback,
            PlanningProgressEvent(kind="failed", error_code=exc.error_code, message=str(exc)),
        )
        raise
