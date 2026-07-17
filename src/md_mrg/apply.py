from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from common.config import AppConfig

MERGE_PLAN_FILE_NAME = "batch_mrg.json"
MERGE_RESULT_FILE_NAME = "batch_mrg_result.json"
MERGED_PDF_PATTERN = "merged-{index:03d}.pdf"
MERGED_MD_PATTERN = "merger-{index:03d}.md"


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


def _merge_group_markdown(source_dir: Path, documents: list[dict[str, Any]], output_markdown: Path) -> None:
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

    output_markdown.write_text("\n\n---\n\n".join(chunks).strip() + "\n", encoding="utf-8")


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


def run_apply(source_dir: Path, cfg: AppConfig) -> dict[str, Any]:
    del cfg

    plan_path = source_dir / MERGE_PLAN_FILE_NAME
    result_path = source_dir / MERGE_RESULT_FILE_NAME

    if not plan_path.exists():
        raise ApplyError("plan_file_not_found", f"Merge plan file does not exist: {plan_path}")

    plan_payload = _read_json_file(plan_path)
    work_items = _validate_document_list(plan_payload, "batch_mrg")

    results: list[dict[str, Any]] = []
    group_index = 0

    for item_index, item in enumerate(work_items, start=1):
        if not _is_group_item(item):
            results.append(
                {
                    "item_index": item_index,
                    "item_type": "pdf",
                    "status": "ok",
                    "document": item,
                }
            )
            continue

        group_index += 1
        documents = item.get("documents", [])
        merged_pdf_name = MERGED_PDF_PATTERN.format(index=group_index)
        merged_md_name = MERGED_MD_PATTERN.format(index=group_index)
        merged_pdf_path = source_dir / merged_pdf_name
        merged_md_path = source_dir / merged_md_name

        try:
            _merge_group_markdown(source_dir, documents, merged_md_path)
            _merge_group_images_to_pdf(source_dir, documents, merged_pdf_path)
            _cleanup_group_markdown(source_dir, documents)
            results.append(
                {
                    "item_index": item_index,
                    "item_type": "group",
                    "status": "ok",
                    "output_pdf": merged_pdf_name,
                    "output_markdown": merged_md_name,
                    "documents": documents,
                }
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
