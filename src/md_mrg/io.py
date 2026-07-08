from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import FragmentRecord


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def validate_fragment_payload(fragment: Any) -> None:
    fragment_dict = _require_dict(fragment, "fragment")
    required_keys = {"sequence_number", "image_file", "markdown_file"}
    missing = sorted(required_keys - set(fragment_dict))
    if missing:
        raise ValueError(f"fragment is missing required keys: {', '.join(missing)}")


def validate_document_payload(document: Any) -> None:
    document_dict = _require_dict(document, "document")
    required_keys = {"document_id", "source_name", "total_pages", "is_verified_sequence", "fragments"}
    missing = sorted(required_keys - set(document_dict))
    if missing:
        raise ValueError(f"document is missing required keys: {', '.join(missing)}")
    fragments = document_dict.get("fragments")
    if not isinstance(fragments, list) or not fragments:
        raise ValueError("document.fragments must be a non-empty array")
    for fragment in fragments:
        validate_fragment_payload(fragment)


def validate_merge_batch_payload(payload: Any) -> None:
    batch_dict = _require_dict(payload, "merge batch")
    required_keys = {"batch_id", "generated_at_utc", "documents"}
    missing = sorted(required_keys - set(batch_dict))
    if missing:
        raise ValueError(f"merge batch is missing required keys: {', '.join(missing)}")
    documents = batch_dict.get("documents")
    if not isinstance(documents, list):
        raise ValueError("merge batch documents must be an array")
    for document in documents:
        validate_document_payload(document)


def load_metadata_documents(md_temp_dir: Path) -> tuple[dict[str, Any], ...]:
    documents: list[dict[str, Any]] = []
    for json_file in sorted(md_temp_dir.glob("*.json"), key=lambda path: path.name.lower()):
        payload = json.loads(json_file.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("documents"), list):
            validate_merge_batch_payload(payload)
            for document in payload["documents"]:
                documents.append(document)
            continue
        if isinstance(payload, dict) and isinstance(payload.get("fragments"), list):
            validate_document_payload(payload)
            documents.append(payload)
            continue
        raise ValueError(f"Unsupported metadata payload in {json_file.name}")
    return tuple(documents)


def split_documents_by_sequence(
    documents: tuple[dict[str, Any], ...],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    verified: list[dict[str, Any]] = []
    loose: list[dict[str, Any]] = []
    for document in documents:
        if bool(document.get("is_verified_sequence", False)):
            verified.append(document)
        else:
            loose.append(document)
    return tuple(verified), tuple(loose)


def flatten_loose_fragments(documents: tuple[dict[str, Any], ...]) -> tuple[FragmentRecord, ...]:
    fragments: list[FragmentRecord] = []
    for document in documents:
        source_document_id = str(document.get("document_id", ""))
        source_name = str(document.get("source_name", "unknown"))
        raw_fragments = document.get("fragments", [])
        if not isinstance(raw_fragments, list):
            continue
        for index, raw_fragment in enumerate(raw_fragments, start=1):
            if not isinstance(raw_fragment, dict):
                continue
            sequence_number = int(raw_fragment.get("sequence_number") or index)
            image_file = str(raw_fragment.get("image_file", ""))
            markdown_file = str(raw_fragment.get("markdown_file", ""))
            anchors = raw_fragment.get("anchors") if isinstance(raw_fragment.get("anchors"), dict) else {}
            content_fingerprint = (
                raw_fragment.get("content_fingerprint")
                if isinstance(raw_fragment.get("content_fingerprint"), dict)
                else {}
            )
            fragment_id = f"{source_document_id}:{sequence_number}:{markdown_file}"
            fragments.append(
                FragmentRecord(
                    source_document_id=source_document_id,
                    source_name=source_name,
                    fragment_id=fragment_id,
                    sequence_number=sequence_number,
                    image_file=image_file,
                    markdown_file=markdown_file,
                    first_line=str(anchors.get("first_line", "")),
                    last_line=str(anchors.get("last_line", "")),
                    snippet=str(content_fingerprint.get("snippet", "")),
                )
            )
    return tuple(sorted(fragments, key=lambda record: record.image_file.lower()))


def write_plan_file(output_path: Path, payload: dict[str, Any], overwrite: bool) -> Path:
    validate_merge_batch_payload(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not overwrite:
        return output_path
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return output_path
