from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from common.config import AppConfig
from md_gen.summarize import summarize_document

MERGE_PLAN_FILE_NAME = "batch_mrg.json"
MERGE_RESULT_FILE_NAME = "batch_mrg_result.json"
MERGED_PDF_PATTERN = "doc_merged_{index:03d}.pdf"
MERGED_MD_PATTERN = "doc_merged_{index:03d}.md"


@dataclass(frozen=True)
class FinalOutput:
    item_index: int
    item_type: str
    output_pdf: str
    output_markdown: str
    summary: str
    source_documents: list[dict[str, Any]]


class ApplyError(RuntimeError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ApplyError("plan_read_failed", f"Failed to read JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ApplyError("plan_invalid_json", f"Invalid JSON in file: {path}") from exc

    if not isinstance(payload, dict):
        raise ApplyError("plan_invalid_shape", f"Expected JSON object in file: {path}")
    return payload


def _validate_document_list(payload: dict[str, Any], file_label: str) -> list[dict[str, Any]]:
    documents = payload.get("documents", [])
    if documents is None:
        return []
    if not isinstance(documents, list):
        raise ApplyError("plan_documents_invalid", f"'{file_label}.documents' must be a list")

    out: list[dict[str, Any]] = []
    for item in documents:
        if isinstance(item, dict):
            out.append(item)
    return out


def _merge_group_markdown(source_dir: Path, documents: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for document in documents:
        markdown_file = document.get("markdown_file")
        if not isinstance(markdown_file, str) or not markdown_file.strip():
            raise ApplyError("group_markdown_missing", "Group document is missing markdown_file")

        markdown_path = source_dir / markdown_file
        try:
            chunks.append(markdown_path.read_text(encoding="utf-8").strip())
        except OSError as exc:
            raise ApplyError("group_markdown_read_failed", f"Failed to read markdown file: {markdown_path}") from exc

    return "\n\n---\n\n".join(chunks).strip()


def _merge_group_images_to_pdf(source_dir: Path, documents: list[dict[str, Any]], output_pdf: Path) -> None:
    images: list[Image.Image] = []
    try:
        for document in documents:
            source_file_name = document.get("source_file_name")
            if not isinstance(source_file_name, str) or not source_file_name.strip():
                raise ApplyError("group_image_missing", "Group document is missing source_file_name")

            image_path = source_dir / source_file_name
            try:
                image = Image.open(image_path)
            except OSError as exc:
                raise ApplyError("group_image_read_failed", f"Failed to open image file: {image_path}") from exc

            images.append(image.convert("RGB"))
            image.close()

        if not images:
            raise ApplyError("group_image_empty", "Cannot merge an empty image group")

        first, rest = images[0], images[1:]
        first.save(output_pdf, format="PDF", save_all=True, append_images=rest)
    finally:
        for image in images:
            image.close()


def _cleanup_group_markdown(source_dir: Path, documents: list[dict[str, Any]]) -> None:
    for document in documents:
        markdown_file = document.get("markdown_file")
        if not isinstance(markdown_file, str) or not markdown_file.strip():
            continue

        markdown_path = source_dir / markdown_file
        try:
            markdown_path.unlink(missing_ok=True)
        except OSError:
            continue


def _is_group_item(item: dict[str, Any]) -> bool:
    return isinstance(item.get("documents"), list)


def _summary_from_pdf_document(document: dict[str, Any]) -> str:
    summary = document.get("summary", "")
    if not isinstance(summary, str):
        return ""
    return summary


def _collect_group_summaries(documents: list[dict[str, Any]]) -> list[str]:
    summaries: list[str] = []
    for document in documents:
        summary = document.get("summary", "")
        if isinstance(summary, str) and summary.strip():
            summaries.append(summary)
    return summaries


def _summarize_group(config: AppConfig, documents: list[dict[str, Any]]) -> str:
    try:
        return summarize_document(config, _collect_group_summaries(documents))
    except Exception as exc:
        raise ApplyError("summary_generation_failed", f"Failed to generate group summary: {exc}") from exc


def _build_abstract_markdown(summary: str, body: str) -> str:
    normalized_body = body.rstrip()
    if normalized_body:
        return f"# Abstract\n\n{summary}\n\n---\n\n{normalized_body}\n"
    return f"# Abstract\n\n{summary}\n\n---\n"


def _plan_pdf_output(document: dict[str, Any]) -> tuple[str, str]:
    source_file_name = document.get("source_file_name")
    if not isinstance(source_file_name, str) or not source_file_name.strip():
        raise ApplyError("pdf_source_missing", "PDF document is missing source_file_name")

    source_name = Path(source_file_name).name
    return source_name, f"{Path(source_name).stem}.md"


def _plan_group_output(group_index: int) -> tuple[str, str]:
    return MERGED_PDF_PATTERN.format(index=group_index), MERGED_MD_PATTERN.format(index=group_index)


def _ensure_can_write(path: Path, overwrite: bool, *, allowed_existing: Path | None = None) -> None:
    if allowed_existing is not None and path == allowed_existing:
        return
    if path.exists() and not overwrite:
        raise ApplyError("output_collision", f"Output already exists: {path}")


def _validate_unique_outputs(outputs: list[tuple[str, str]]) -> None:
    seen: set[str] = set()
    for output_pdf, output_markdown in outputs:
        for output_name in (output_pdf, output_markdown):
            normalized = output_name.lower()
            if normalized in seen:
                raise ApplyError("output_cardinality_invalid", f"Duplicate planned output artifact: {output_name}")
            seen.add(normalized)


def _final_output_to_result(output: FinalOutput, source_key: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "item_index": output.item_index,
        "item_type": output.item_type,
        "status": "ok",
        "output_pdf": output.output_pdf,
        "output_markdown": output.output_markdown,
        "summary": output.summary,
    }
    if source_key == "document":
        result["document"] = output.source_documents[0]
    else:
        result["documents"] = output.source_documents
    return result


def _read_pdf_markdown_body(source_dir: Path, document: dict[str, Any]) -> tuple[Path, str]:
    markdown_file = document.get("markdown_file")
    if not isinstance(markdown_file, str) or not markdown_file.strip():
        raise ApplyError("pdf_markdown_missing", "PDF document is missing markdown_file")

    markdown_path = source_dir / markdown_file
    try:
        return markdown_path, markdown_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ApplyError("pdf_markdown_read_failed", f"Failed to read markdown file: {markdown_path}") from exc


def _validate_planned_outputs(work_items: list[dict[str, Any]]) -> None:
    outputs: list[tuple[str, str]] = []
    group_index = 0
    for item in work_items:
        if _is_group_item(item):
            group_index += 1
            outputs.append(_plan_group_output(group_index))
            continue
        outputs.append(_plan_pdf_output(item))

    _validate_unique_outputs(outputs)


def run_apply(source_dir: Path, cfg: AppConfig) -> dict[str, Any]:
    plan_path = source_dir / MERGE_PLAN_FILE_NAME
    result_path = source_dir / MERGE_RESULT_FILE_NAME

    if not plan_path.exists():
        raise ApplyError("plan_file_not_found", f"Merge plan file does not exist: {plan_path}")

    plan_payload = _read_json_file(plan_path)
    work_items = _validate_document_list(plan_payload, "batch_mrg")
    _validate_planned_outputs(work_items)
    _ensure_can_write(result_path, cfg.runtime.overwrite)

    results: list[dict[str, Any]] = []
    group_index = 0

    for item_index, item in enumerate(work_items, start=1):
        if not _is_group_item(item):
            output_pdf_name, output_markdown_name = _plan_pdf_output(item)
            source_pdf_path = source_dir / output_pdf_name
            if not source_pdf_path.exists():
                raise ApplyError("pdf_source_not_found", f"PDF source file does not exist: {source_pdf_path}")

            input_markdown_path, markdown_body = _read_pdf_markdown_body(source_dir, item)
            output_markdown_path = source_dir / output_markdown_name
            _ensure_can_write(output_markdown_path, cfg.runtime.overwrite, allowed_existing=input_markdown_path)
            summary = _summary_from_pdf_document(item)
            output_markdown_path.write_text(_build_abstract_markdown(summary, markdown_body), encoding="utf-8")
            results.append(
                _final_output_to_result(
                    FinalOutput(
                        item_index=item_index,
                        item_type="pdf",
                        output_pdf=output_pdf_name,
                        output_markdown=output_markdown_name,
                        summary=summary,
                        source_documents=[item],
                    ),
                    "document",
                )
            )
            continue

        group_index += 1
        documents = item.get("documents", [])
        merged_pdf_name, merged_md_name = _plan_group_output(group_index)
        merged_pdf_path = source_dir / merged_pdf_name
        merged_md_path = source_dir / merged_md_name

        try:
            _ensure_can_write(merged_md_path, cfg.runtime.overwrite)
            _ensure_can_write(merged_pdf_path, cfg.runtime.overwrite)
            summary = _summarize_group(cfg, documents)
            markdown_body = _merge_group_markdown(source_dir, documents)
            merged_md_path.write_text(_build_abstract_markdown(summary, markdown_body), encoding="utf-8")
            _merge_group_images_to_pdf(source_dir, documents, merged_pdf_path)
            _cleanup_group_markdown(source_dir, documents)
            results.append(
                _final_output_to_result(
                    FinalOutput(
                        item_index=item_index,
                        item_type="group",
                        output_pdf=merged_pdf_name,
                        output_markdown=merged_md_name,
                        summary=summary,
                        source_documents=documents,
                    ),
                    "documents",
                )
            )
        except ApplyError as exc:
            results.append(
                {
                    "item_index": item_index,
                    "item_type": "group",
                    "status": "failed",
                    "error_code": exc.error_code,
                    "message": str(exc),
                    "documents": documents,
                }
            )

    output_payload = {"items": results}
    result_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_payload
