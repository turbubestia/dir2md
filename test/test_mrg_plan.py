import json
from pathlib import Path

from PIL import Image

from md_mrg.apply import apply_merge_plan
from md_mrg.cli import main
from md_mrg.io import validate_document_payload, validate_merge_batch_payload


def _write_document_metadata(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def test_mrg_plan_builds_merge_plan_from_loose_documents(tmp_path, monkeypatch) -> None:
    md_temp = tmp_path / "md-temp"
    mg_temp = tmp_path / "mg-temp"
    md_temp.mkdir(parents=True)

    _write_document_metadata(
        md_temp / "scan001.json",
        {
            "document_id": "doc-a",
            "source_name": "scan001.jpg",
            "total_pages": 1,
            "is_verified_sequence": False,
            "fragments": [
                {
                    "sequence_number": 1,
                    "image_file": "scan001.jpg",
                    "markdown_file": "scan001.md",
                    "anchors": {
                        "first_line": "utility provider statement",
                        "last_line": "total amount due is",
                    },
                    "content_fingerprint": {
                        "snippet": "utility invoice july",
                        "detected_entities": [],
                    },
                }
            ],
        },
    )
    _write_document_metadata(
        md_temp / "scan002.json",
        {
            "document_id": "doc-b",
            "source_name": "scan002.jpg",
            "total_pages": 1,
            "is_verified_sequence": False,
            "fragments": [
                {
                    "sequence_number": 1,
                    "image_file": "scan002.jpg",
                    "markdown_file": "scan002.md",
                    "anchors": {
                        "first_line": "total amount due is 100.00",
                        "last_line": "please pay before due date",
                    },
                    "content_fingerprint": {
                        "snippet": "utility invoice july amount 100.00",
                        "detected_entities": [],
                    },
                }
            ],
        },
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "md-mrg",
            "plan",
            "--md-temp-dir",
            str(md_temp),
            "--mg-temp-dir",
            str(mg_temp),
            "--edge-scorer",
            "heuristic",
            "--overwrite",
        ],
    )

    exit_code = main()
    assert exit_code == 0

    plan_file = mg_temp / "merge-plan.json"
    assert plan_file.exists()
    payload = json.loads(plan_file.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "2.0"
    assert payload["scorer_mode"] == "heuristic"
    assert isinstance(payload["documents"], list)
    assert len(payload["documents"]) >= 1


def test_mrg_apply_merges_markdown_with_separator(tmp_path: Path) -> None:
    md_temp = tmp_path / "md-temp"
    out_dir = tmp_path / "out"
    im_temp = tmp_path / "im-temp"
    md_temp.mkdir(parents=True)
    im_temp.mkdir(parents=True)
    (md_temp / "a.md").write_text("Page A", encoding="utf-8")
    (md_temp / "b.md").write_text("Page B", encoding="utf-8")
    Image.new("RGB", (200, 300), color=(255, 255, 255)).save(im_temp / "a.jpg")
    Image.new("RGB", (200, 300), color=(255, 255, 255)).save(im_temp / "b.jpg")

    batch_file = tmp_path / "merge-plan.json"
    batch_file.write_text(
        json.dumps(
            {
                "batch_id": "batch-1",
                "generated_at_utc": "2026-07-07T00:00:00+00:00",
                "md_temp_dir": str(md_temp),
                "im_temp_dir": str(im_temp),
                "documents": [
                    {
                        "document_id": "doc-1",
                        "source_name": "scan.jpg",
                        "total_pages": 2,
                        "is_verified_sequence": True,
                        "fragments": [
                            {
                                "sequence_number": 1,
                                "image_file": "a.jpg",
                                "markdown_file": "a.md",
                                "content_fingerprint": {"snippet": "invoice july 1", "detected_entities": []},
                            },
                            {
                                "sequence_number": 2,
                                "image_file": "b.jpg",
                                "markdown_file": "b.md",
                                "content_fingerprint": {"snippet": "invoice july 2", "detected_entities": []},
                            },
                        ],
                    }
                ],
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = apply_merge_plan(
        merge_batch_file=batch_file,
        output_dir=out_dir,
        md_temp_dir=None,
        overwrite=True,
    )
    assert exit_code == 0

    merged_markdown_files = list(out_dir.glob("*.md"))
    assert len(merged_markdown_files) == 1
    merged_markdown = merged_markdown_files[0]
    content = merged_markdown.read_text(encoding="utf-8")
    assert "Page A" in content
    assert "\n\n---\n\n" in content
    assert "Page B" in content

    assert len(tuple(out_dir.glob("*.pdf"))) == 1


def test_validate_merge_batch_payload_rejects_missing_documents() -> None:
    try:
        validate_merge_batch_payload({"batch_id": "batch-1", "generated_at_utc": "now"})
    except ValueError as exc:
        assert "documents" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid merge batch payload")


def test_validate_document_payload_rejects_missing_fragment_keys() -> None:
    try:
        validate_document_payload(
            {
                "document_id": "doc-1",
                "source_name": "scan.jpg",
                "total_pages": 1,
                "is_verified_sequence": True,
                "fragments": [{"image_file": "a.jpg"}],
            }
        )
    except ValueError as exc:
        assert "sequence_number" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid document payload")
