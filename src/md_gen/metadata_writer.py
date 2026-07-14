# from __future__ import annotations

# import json
# import re
# import uuid
# from dataclasses import dataclass
# from hashlib import sha1
# from pathlib import Path

# from common.gateway import OcrResponse
# from .markdown_writer import PersistedMarkdownRecord

# _ALLOWED_TEXT_CHARS = re.compile(r"[^a-zA-Z0-9 .\-]+")
# _MAX_ANCHOR_WORDS = 20


# @dataclass(frozen=True)
# class PersistedMetadataRecord:
#     source_file_path: Path
#     output_json_path: Path
#     was_written: bool


# def _sanitize_stem(path: Path) -> str:
#     cleaned = []
#     for char in path.stem.lower():
#         if char.isalnum() or char in {"-", "_"}:
#             cleaned.append(char)
#         else:
#             cleaned.append("-")
#     return "".join(cleaned).strip("-") or "document"


# def _normalize_plain_text(value: str) -> str:
#     cleaned = value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
#     return " ".join(cleaned.split())


# def _truncate_words(value: str, max_words: int = _MAX_ANCHOR_WORDS) -> str:
#     words = value.split()
#     if len(words) <= max_words:
#         return value
#     return " ".join(words[:max_words])


# def _extract_anchor_lines(markdown_text: str) -> tuple[str, str]:
#     normalized_lines = []
#     for raw_line in markdown_text.splitlines():
#         normalized = _normalize_plain_text(raw_line)
#         if normalized:
#             normalized_lines.append(normalized)

#     if not normalized_lines:
#         return "", ""

#     first_line = _truncate_words(normalized_lines[0])
#     last_line = _truncate_words(normalized_lines[-1])
#     return first_line, last_line


# def _build_document_output_json_path(metadata_temp_dir: Path, source_file_path: Path) -> Path:
#     source_hash = sha1(source_file_path.as_posix().encode("utf-8")).hexdigest()[:10]
#     filename = f"{_sanitize_stem(source_file_path)}-{source_hash}.json"
#     return metadata_temp_dir / filename


# def _build_document_id(source_file_path: Path) -> str:
#     return str(uuid.uuid5(uuid.NAMESPACE_URL, source_file_path.as_posix()))


# def persist_document_metadata(
#     markdown_records: tuple[PersistedMarkdownRecord, ...],
#     ocr_responses: tuple[OcrResponse, ...],
#     summary_by_image_path: dict[Path, str],
#     metadata_temp_dir: Path,
#     overwrite: bool,
# ) -> tuple[PersistedMetadataRecord, ...]:
#     metadata_temp_dir.mkdir(parents=True, exist_ok=True)

#     ocr_by_image = {response.image_path.resolve(): response for response in ocr_responses}
#     grouped: dict[Path, list[PersistedMarkdownRecord]] = {}
#     for record in markdown_records:
#         grouped.setdefault(record.source_file_path.resolve(), []).append(record)

#     persisted: list[PersistedMetadataRecord] = []

#     for source_file_path in sorted(grouped, key=lambda path: path.as_posix().lower()):
#         raw_records = grouped[source_file_path]
#         deduped_records: list[PersistedMarkdownRecord] = []
#         seen_fragment_keys: set[tuple[str, str, str, int | None]] = set()
#         for record in raw_records:
#             fragment_key = (
#                 record.source_file_path.resolve().as_posix(),
#                 record.source_image_path.resolve().as_posix(),
#                 record.output_markdown_path.resolve().as_posix(),
#                 record.source_page_index,
#             )
#             if fragment_key in seen_fragment_keys:
#                 continue
#             seen_fragment_keys.add(fragment_key)
#             deduped_records.append(record)

#         records = deduped_records
#         records.sort(
#             key=lambda record: (
#                 record.source_page_index if record.source_page_index is not None else 0,
#                 record.output_markdown_path.name,
#             )
#         )

#         print(f"> processing source metadata {source_file_path}")

#         fragments = []
#         for record in records:
#             ocr_response = ocr_by_image.get(record.source_image_path.resolve())
#             markdown_text = ocr_response.markdown_text if ocr_response is not None else ""
#             first_line, last_line = _extract_anchor_lines(markdown_text)
#             summary_text = _normalize_plain_text(summary_by_image_path.get(record.source_image_path.resolve(), ""))
#             sequence_number = (record.source_page_index + 1) if record.source_page_index is not None else 1

#             fragments.append(
#                 {
#                     "sequence_number": sequence_number,
#                     "image_file": record.source_image_path.name,
#                     "markdown_file": record.output_markdown_path.name,
#                     "anchors": {
#                         "first_line": first_line,
#                         "last_line": last_line,
#                         "page_header": "",
#                         "page_footer": "",
#                     },
#                     "content_fingerprint": {
#                         "snippet": summary_text,
#                         "detected_entities": [],
#                     },
#                 }
#             )

#         is_verified_sequence = all(record.source_type == "pdf_page" for record in records)
#         payload = {
#             "document_id": _build_document_id(source_file_path),
#             "source_name": source_file_path.name,
#             "total_pages": len(fragments),
#             "is_verified_sequence": is_verified_sequence,
#             "fragments": fragments,
#         }

#         output_json_path = _build_document_output_json_path(
#             metadata_temp_dir=metadata_temp_dir,
#             source_file_path=source_file_path,
#         )
#         if output_json_path.exists() and not overwrite:
#             print(f"> skipping file {output_json_path}: already exist")
#             was_written = False
#         else:
#             output_json_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
#             was_written = True

#         persisted.append(
#             PersistedMetadataRecord(
#                 source_file_path=source_file_path,
#                 output_json_path=output_json_path,
#                 was_written=was_written,
#             )
#         )

#     return tuple(persisted)
