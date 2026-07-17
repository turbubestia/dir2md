from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common.config import MdMrgConfig
from common.gateway import GatewayError, LlamaLanguageGateway, TextRequest

BATCH_FILE_NAME = "batch.json"
MERGE_PLAN_FILE_NAME = "batch_mrg.json"
SCORE_THRESHOLD = 5.0


class PlannerError(RuntimeError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class ScoreOutcome:
    score: float | None
    error_code: str | None = None
    detail: str | None = None


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

    score = payload.get("score")
    if not isinstance(score, (int, float)):
        raise PlannerError("score_parse_failed", "Score response must contain numeric 'score'")

    return float(score)


def _score_pair(
    source_dir: Path,
    gateway: LlamaLanguageGateway,
    score_prompt: str,
    page_a: dict[str, Any],
    page_b: dict[str, Any],
) -> ScoreOutcome:
    try:
        page_a_text = _load_markdown(source_dir, page_a)
        page_b_text = _load_markdown(source_dir, page_b)

        request = TextRequest(
            system_prompt=score_prompt,
            user_prompt=_build_score_user_prompt(page_a_text=page_a_text, page_b_text=page_b_text),
        )
        response = gateway.send_text_request(request)
        score = _parse_score_response(response.text)
        return ScoreOutcome(score=score)
    except PlannerError as exc:
        return ScoreOutcome(score=None, error_code=exc.error_code, detail=str(exc))
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


def _build_groups(
    source_dir: Path,
    gateway: LlamaLanguageGateway,
    score_prompt: str,
    image_documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not image_documents:
        return []

    groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = [image_documents[0]]

    left_index = 0
    right_index = 1

    while right_index < len(image_documents):
        page_a = image_documents[left_index]
        page_b = image_documents[right_index]
        score_outcome = _score_pair(source_dir, gateway, score_prompt, page_a, page_b)

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


def run_plan(source_dir: Path, cfg: MdMrgConfig) -> dict[str, Any]:
    batch_path = source_dir / BATCH_FILE_NAME
    plan_path = source_dir / MERGE_PLAN_FILE_NAME

    if not batch_path.exists():
        raise PlannerError("batch_file_not_found", f"Input batch file does not exist: {batch_path}")

    payload = _read_json_file(batch_path)
    documents = _validate_document_list(payload, "batch")
    image_documents, pdf_documents = _partition_documents(documents)

    with LlamaLanguageGateway(
        endpoint_url=cfg.language_model.endpoint_url,
        model_name=cfg.language_model.model_name,
    ) as gateway:
        gateway.request_timeout_seconds = cfg.language_model.request_timeout_seconds
        gateway.request_max_retries = cfg.language_model.request_max_retries
        groups = _build_groups(
            source_dir=source_dir,
            gateway=gateway,
            score_prompt=cfg.md_mrg.score_prompt_text,
            image_documents=image_documents,
        )

    merged_documents: list[dict[str, Any]] = []
    merged_documents.extend(groups)
    merged_documents.extend(pdf_documents)

    output_payload = {"documents": merged_documents}
    plan_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return output_payload
