# import json
# from pathlib import Path

# from common.gateway import OcrResponse
# from md_gen.markdown_writer import PersistedMarkdownRecord
# from md_gen.metadata_writer import persist_document_metadata


# def _record(
#     image_path: Path,
#     source_file_path: Path,
#     source_type: str,
#     source_page_index: int | None,
#     output_markdown_path: Path,
# ) -> PersistedMarkdownRecord:
#     return PersistedMarkdownRecord(
#         source_image_path=image_path,
#         source_file_path=source_file_path,
#         source_type=source_type,
#         source_page_index=source_page_index,
#         output_markdown_path=output_markdown_path,
#         estimated_vision_tokens=123,
#         was_written=True,
#     )


# def test_persist_document_metadata_groups_pdf_pages_in_single_json(tmp_path: Path) -> None:
#     source_pdf = tmp_path / "invoice.pdf"
#     source_pdf.write_bytes(b"pdf")

#     image_1 = tmp_path / "im-temp" / "invoice-aaa-p0001.png"
#     image_2 = tmp_path / "im-temp" / "invoice-aaa-p0002.png"
#     image_1.parent.mkdir(parents=True, exist_ok=True)
#     image_1.write_bytes(b"x")
#     image_2.write_bytes(b"x")

#     md_1 = tmp_path / "md-temp" / "invoice-p0001-hash.md"
#     md_2 = tmp_path / "md-temp" / "invoice-p0002-hash.md"
#     md_1.parent.mkdir(parents=True, exist_ok=True)
#     md_1.write_text("page 1", encoding="utf-8")
#     md_2.write_text("page 2", encoding="utf-8")

#     records = (
#         _record(image_1, source_pdf, "pdf_page", 0, md_1),
#         _record(image_2, source_pdf, "pdf_page", 1, md_2),
#     )
#     ocr_responses = (
#         OcrResponse(image_path=image_1, model_name="lightonocr-2", markdown_text="HEADER\nLine A", raw_response={}),
#         OcrResponse(image_path=image_2, model_name="lightonocr-2", markdown_text="Line B\nFOOTER", raw_response={}),
#     )
#     summaries = {
#         image_1.resolve(): "invoice summary 1",
#         image_2.resolve(): "invoice summary 2",
#     }

#     persisted = persist_document_metadata(
#         markdown_records=records,
#         ocr_responses=ocr_responses,
#         summary_by_image_path=summaries,
#         metadata_temp_dir=tmp_path / "metadata-temp",
#         overwrite=True,
#     )

#     assert len(persisted) == 1
#     payload = json.loads(persisted[0].output_json_path.read_text(encoding="utf-8"))
#     assert payload["source_name"] == "invoice.pdf"
#     assert payload["total_pages"] == 2
#     assert payload["is_verified_sequence"] is True
#     assert len(payload["fragments"]) == 2
#     assert payload["fragments"][0]["sequence_number"] == 1
#     assert payload["fragments"][1]["sequence_number"] == 2
#     assert payload["fragments"][0]["content_fingerprint"]["detected_entities"] == []


# def test_persist_document_metadata_marks_single_image_as_unverified_sequence(tmp_path: Path) -> None:
#     source_image = tmp_path / "scan001.jpg"
#     source_image.write_bytes(b"x")

#     processed_image = tmp_path / "im-temp" / "scan001-hash.jpg"
#     processed_image.parent.mkdir(parents=True, exist_ok=True)
#     processed_image.write_bytes(b"x")

#     markdown_output = tmp_path / "md-temp" / "scan001-hash.md"
#     markdown_output.parent.mkdir(parents=True, exist_ok=True)
#     markdown_output.write_text("scan markdown", encoding="utf-8")

#     records = (
#         _record(processed_image, source_image, "image", None, markdown_output),
#     )
#     ocr_responses = (
#         OcrResponse(
#             image_path=processed_image,
#             model_name="lightonocr-2",
#             markdown_text="*** HEADER ***\nValue line 123\nTrailer@@",
#             raw_response={},
#         ),
#     )

#     persisted = persist_document_metadata(
#         markdown_records=records,
#         ocr_responses=ocr_responses,
#         summary_by_image_path={processed_image.resolve(): "summary [bad] chars? OK-12."},
#         metadata_temp_dir=tmp_path / "metadata-temp",
#         overwrite=True,
#     )

#     payload = json.loads(persisted[0].output_json_path.read_text(encoding="utf-8"))
#     assert payload["total_pages"] == 1
#     assert payload["is_verified_sequence"] is False
#     fragment = payload["fragments"][0]
#     assert fragment["sequence_number"] == 1
#     assert fragment["anchors"]["first_line"] == "HEADER"
#     assert fragment["anchors"]["last_line"] == "Trailer"
#     assert fragment["content_fingerprint"]["snippet"] == "summary bad chars OK-12."


# def test_persist_document_metadata_deduplicates_duplicate_fragment_records(tmp_path: Path) -> None:
#     source_image = tmp_path / "scan002.jpg"
#     source_image.write_bytes(b"x")

#     processed_image = tmp_path / "im-temp" / "scan002-hash.jpg"
#     processed_image.parent.mkdir(parents=True, exist_ok=True)
#     processed_image.write_bytes(b"x")

#     markdown_output = tmp_path / "md-temp" / "scan002-hash.md"
#     markdown_output.parent.mkdir(parents=True, exist_ok=True)
#     markdown_output.write_text("scan markdown", encoding="utf-8")

#     duplicate_record = _record(processed_image, source_image, "image", None, markdown_output)
#     records = (duplicate_record, duplicate_record)
#     ocr_responses = (
#         OcrResponse(
#             image_path=processed_image,
#             model_name="lightonocr-2",
#             markdown_text="HEADER\nBody\nTrailer",
#             raw_response={},
#         ),
#     )

#     persisted = persist_document_metadata(
#         markdown_records=records,
#         ocr_responses=ocr_responses,
#         summary_by_image_path={processed_image.resolve(): "summary"},
#         metadata_temp_dir=tmp_path / "metadata-temp",
#         overwrite=True,
#     )

#     payload = json.loads(persisted[0].output_json_path.read_text(encoding="utf-8"))
#     assert payload["total_pages"] == 1
#     assert len(payload["fragments"]) == 1
