import json
from pathlib import Path

from PIL import Image
import pytest

from common.config import AppConfig, ImageSettings, LlamaModelSettings, MdGenSettings, MdMrgSettings, PathSettings, PromptSettings, RuntimeSettings
from md_mrg import apply as apply_mod
from md_mrg import planner as planner_mod


def _cfg(source_dir: Path, *, overwrite: bool = False) -> AppConfig:
    prompt_file = source_dir / "prompt.md"
    prompt_file.write_text("score prompt", encoding="utf-8")
    return AppConfig(
        paths=PathSettings(source_dir=source_dir, output_dir=source_dir),
        ocr_model=LlamaModelSettings(
            endpoint_url="http://localhost:8080/v1/chat/completions",
            model_name="lightonocr-2",
            request_timeout_seconds=30.0,
            request_max_retries=0,
        ),
        language_model=LlamaModelSettings(
            endpoint_url="http://localhost:8081/v1/chat/completions",
            model_name="qwen3-1.7b",
            request_timeout_seconds=30.0,
            request_max_retries=0,
        ),
        md_gen=MdGenSettings(
            prompts=PromptSettings(summary_prompt_path=None, summary_prompt_text="summary"),
            image=ImageSettings(max_longest_edge_px=1540, token_threshold=4096),
        ),
        md_mrg=MdMrgSettings(
            score=PromptSettings(
                summary_prompt_path=prompt_file,
                summary_prompt_text="score prompt",
            ),
        ),
        runtime=RuntimeSettings(dry_run=False, overwrite=overwrite),
    )


def _image_doc(stem: str, *, summary: str = "") -> dict:
    return {
        "source_file_name": f"{stem}.jpg",
        "file_type": "image",
        "page_count": 1,
        "date_of_process": "2026-07-14T08:21:54.244888+00:00",
        "summary": summary,
        "markdown_file": f"{stem}.md",
        "status": "ok",
    }


def _write_image_and_markdown(source_dir: Path, stem: str, text: str) -> dict:
    image_doc = _image_doc(stem)
    Image.new("RGB", (200, 300), color=(255, 255, 255)).save(source_dir / f"{stem}.jpg")
    (source_dir / f"{stem}.md").write_text(text, encoding="utf-8")
    return image_doc


def test_score_prompt_envelope_exact_markers() -> None:
    prompt = planner_mod._build_score_user_prompt("A", "B")

    assert "# Page A content" in prompt
    assert "--- start of Page A content ---" in prompt
    assert "--- end of Page A content ---" in prompt
    assert "# Page B content" in prompt
    assert "--- start of Page B content ---" in prompt
    assert "--- end of Page B content ---" in prompt


def test_parse_score_response_requires_json_numeric_score() -> None:
    assert planner_mod._parse_score_response('{"bridge_score": 5}') == 5.0
    assert planner_mod._parse_score_response('{"score": 5}') == 5.0

    with pytest.raises(planner_mod.PlannerError, match="valid JSON"):
        planner_mod._parse_score_response("not-json")

    with pytest.raises(planner_mod.PlannerError, match="numeric 'score'"):
        planner_mod._parse_score_response('{"score": "high"}')


def test_apply_writes_deterministic_outputs_and_deletes_only_group_markdown(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()

    doc_a = _write_image_and_markdown(source_dir, "a", "Page A")
    doc_b = _write_image_and_markdown(source_dir, "b", "Page B")

    pdf_doc = {
        "source_file_name": "done.pdf",
        "file_type": "pdf",
        "page_count": 3,
        "date_of_process": "2026-07-14T08:21:54.244888+00:00",
        "summary": "done",
        "markdown_file": "done.md",
        "status": "ok",
    }
    (source_dir / "done.pdf").write_bytes(b"%PDF-1.4")
    (source_dir / "done.md").write_text("done", encoding="utf-8")

    (source_dir / "batch_mrg.json").write_text(
        json.dumps({"documents": [{"documents": [doc_a, doc_b]}, pdf_doc]}, indent=2),
        encoding="utf-8",
    )

    out = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert (source_dir / "doc_merged_001.md").exists()
    assert (source_dir / "doc_merged_001.pdf").exists()
    merged_markdown = (source_dir / "doc_merged_001.md").read_text(encoding="utf-8")
    assert merged_markdown.startswith("# Abstract\n\n\n\n---\n\n")
    assert "Page A" in merged_markdown
    assert "Page B" in merged_markdown

    assert not (source_dir / "a.md").exists()
    assert not (source_dir / "b.md").exists()

    assert (source_dir / "a.jpg").exists()
    assert (source_dir / "b.jpg").exists()

    result_file = source_dir / "batch_mrg_result.json"
    assert result_file.exists()
    payload = json.loads(result_file.read_text(encoding="utf-8"))
    assert payload == out
    assert payload["items"][0]["status"] == "ok"
    assert payload["items"][0]["output_pdf"] == "doc_merged_001.pdf"
    assert payload["items"][0]["output_markdown"] == "doc_merged_001.md"
    assert payload["items"][0]["summary"] == ""
    assert payload["items"][1]["item_type"] == "pdf"
    assert payload["items"][1]["output_pdf"] == "done.pdf"
    assert payload["items"][1]["output_markdown"] == "done.md"
    assert payload["items"][1]["summary"] == "done"


def test_apply_continues_after_failed_group(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()

    ok_a = _write_image_and_markdown(source_dir, "ok-a", "OK A")
    ok_b = _write_image_and_markdown(source_dir, "ok-b", "OK B")

    bad_a = _write_image_and_markdown(source_dir, "bad-a", "BAD A")
    bad_b = _image_doc("bad-b")
    Image.new("RGB", (200, 300), color=(255, 255, 255)).save(source_dir / "bad-b.jpg")

    (source_dir / "batch_mrg.json").write_text(
        json.dumps(
            {
                "documents": [
                    {"documents": [bad_a, bad_b]},
                    {"documents": [ok_a, ok_b]},
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert payload["items"][0]["status"] == "failed"
    assert payload["items"][1]["status"] == "ok"
    assert (source_dir / "doc_merged_002.pdf").exists()
    assert (source_dir / "doc_merged_002.md").exists()


def test_apply_accepts_reordered_singleton_and_multiple_image_groups(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    page_a = _write_image_and_markdown(source_dir, "page-a", "Page A")
    page_b = _write_image_and_markdown(source_dir, "page-b", "Page B")
    page_c = _write_image_and_markdown(source_dir, "page-c", "Page C")

    (source_dir / "batch_mrg.json").write_text(
        json.dumps(
            {
                "documents": [
                    {"documents": [page_b, page_a]},
                    {"documents": [page_c]},
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert [item["status"] for item in payload["items"]] == ["ok", "ok"]
    assert payload["items"][0]["documents"] == [page_b, page_a]
    assert payload["items"][1]["documents"] == [page_c]
    assert (source_dir / "doc_merged_001.pdf").exists()
    assert (source_dir / "doc_merged_002.pdf").exists()


def test_build_abstract_markdown_prepends_exact_block_and_preserves_existing_abstract() -> None:
    body = "# Abstract\n\nOriginal abstract\n\n# Body\n\nText"

    assert apply_mod._build_abstract_markdown("Normalized summary", body) == (
        "# Abstract\n\n"
        "Normalized summary\n\n"
        "---\n\n"
        "# Abstract\n\n"
        "Original abstract\n\n"
        "# Body\n\n"
        "Text\n"
    )


def test_apply_pdf_item_uses_source_pdf_name_markdown_name_and_summary_without_gateway(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    pdf_doc = {
        "source_file_name": "my_file.pdf",
        "file_type": "pdf",
        "page_count": 3,
        "date_of_process": "2026-07-14T08:21:54.244888+00:00",
        "summary": "PDF summary",
        "markdown_file": "ocr-output.md",
        "status": "ok",
    }
    (source_dir / "my_file.pdf").write_bytes(b"%PDF-1.4")
    (source_dir / "ocr-output.md").write_text("PDF body", encoding="utf-8")
    (source_dir / "batch_mrg.json").write_text(json.dumps({"documents": [pdf_doc]}), encoding="utf-8")

    def fail_summary(*args, **kwargs):
        raise AssertionError("PDF-backed items must not request language summaries")

    monkeypatch.setattr(apply_mod, "summarize_document", fail_summary, raising=False)

    payload = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert payload["items"] == [
        {
            "item_index": 1,
            "item_type": "pdf",
            "status": "ok",
            "output_pdf": "my_file.pdf",
            "output_markdown": "my_file.md",
            "summary": "PDF summary",
            "document": pdf_doc,
        }
    ]
    assert (source_dir / "my_file.md").read_text(encoding="utf-8") == "# Abstract\n\nPDF summary\n\n---\n\nPDF body\n"


def test_apply_copies_pdf_from_original_source_and_reports_progress(tmp_path: Path) -> None:
    original_source = tmp_path / "source"
    output_dir = tmp_path / "out"
    (original_source / "nested").mkdir(parents=True)
    output_dir.mkdir()
    pdf_doc = {
        "source_file_name": "nested/original.pdf",
        "file_type": "pdf",
        "page_count": 2,
        "date_of_process": "2026-07-14T08:21:54.244888+00:00",
        "summary": "Original summary",
        "markdown_file": "original-ocr.md",
        "status": "ok",
    }
    (original_source / "nested" / "original.pdf").write_bytes(b"%PDF-1.4 original")
    (output_dir / "original-ocr.md").write_text("Original body", encoding="utf-8")
    (output_dir / "batch_mrg.json").write_text(json.dumps({"documents": [pdf_doc]}), encoding="utf-8")
    events: list[apply_mod.ApplyProgressEvent] = []

    payload = apply_mod.run_apply(source_dir=output_dir, cfg=_cfg(original_source), progress_callback=events.append)

    assert [event.kind for event in events] == ["stage_start", "item_start", "item_complete", "result_persisted", "complete"]
    assert events[2].output_pdf == "original.pdf"
    assert events[2].output_markdown == "original.md"
    assert events[-1].completed_items == 1
    assert (original_source / "nested" / "original.pdf").read_bytes() == b"%PDF-1.4 original"
    assert (output_dir / "original.pdf").read_bytes() == b"%PDF-1.4 original"
    assert (output_dir / "original.md").read_text(encoding="utf-8") == "# Abstract\n\nOriginal summary\n\n---\n\nOriginal body\n"
    assert payload["items"][0]["output_pdf"] == "original.pdf"


def test_apply_group_pdf_uses_original_source_images_and_output_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original_source = tmp_path / "source"
    output_dir = tmp_path / "out"
    original_source.mkdir()
    output_dir.mkdir()
    doc_a = _image_doc("source-a", summary="Summary A")
    doc_b = _image_doc("source-b", summary="Summary B")
    Image.new("RGB", (200, 300), color=(255, 255, 255)).save(original_source / "source-a.jpg")
    Image.new("RGB", (200, 300), color=(255, 255, 255)).save(original_source / "source-b.jpg")
    (output_dir / "source-a.md").write_text("Page A", encoding="utf-8")
    (output_dir / "source-b.md").write_text("Page B", encoding="utf-8")
    (output_dir / "batch_mrg.json").write_text(json.dumps({"documents": [{"documents": [doc_a, doc_b]}]}), encoding="utf-8")

    monkeypatch.setattr(apply_mod, "summarize_document", lambda config, summaries: "Group summary", raising=False)

    payload = apply_mod.run_apply(source_dir=output_dir, cfg=_cfg(original_source))

    assert payload["items"][0]["status"] == "ok"
    assert (output_dir / "doc_merged_001.pdf").exists()
    assert (output_dir / "doc_merged_001.md").read_text(encoding="utf-8") == "# Abstract\n\nGroup summary\n\n---\n\nPage A\n\n---\n\nPage B\n"
    assert not (output_dir / "source-a.jpg").exists()
    assert not (output_dir / "source-b.jpg").exists()
    assert (original_source / "source-a.jpg").exists()
    assert (original_source / "source-b.jpg").exists()


def test_apply_group_summary_skips_blank_summaries_and_preserves_plan_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    page_a = _write_image_and_markdown(source_dir, "page-a", "Page A")
    page_b = _write_image_and_markdown(source_dir, "page-b", "Page B")
    page_c = _write_image_and_markdown(source_dir, "page-c", "Page C")
    page_a["summary"] = "Summary A"
    page_b["summary"] = "   "
    page_c["summary"] = "Summary C"
    seen_summaries: list[list[str]] = []

    def fake_summarize_document(config: AppConfig, page_summaries: list[str]) -> str:
        seen_summaries.append(page_summaries)
        return "Group summary"

    monkeypatch.setattr(apply_mod, "summarize_document", fake_summarize_document, raising=False)
    (source_dir / "batch_mrg.json").write_text(
        json.dumps({"documents": [{"documents": [page_c, page_b, page_a]}]}),
        encoding="utf-8",
    )

    payload = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert seen_summaries == [["Summary C", "Summary A"]]
    assert payload["items"][0]["summary"] == "Group summary"
    assert (source_dir / "doc_merged_001.md").read_text(encoding="utf-8").startswith("# Abstract\n\nGroup summary\n\n---\n\n")


def test_apply_result_summary_matches_persisted_abstract(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    pdf_doc = {
        "source_file_name": "result.pdf",
        "file_type": "pdf",
        "page_count": 1,
        "date_of_process": "2026-07-14T08:21:54.244888+00:00",
        "summary": "Persisted summary",
        "markdown_file": "result-source.md",
        "status": "ok",
    }
    (source_dir / "result.pdf").write_bytes(b"%PDF-1.4")
    (source_dir / "result-source.md").write_text("Body", encoding="utf-8")
    (source_dir / "batch_mrg.json").write_text(json.dumps({"documents": [pdf_doc]}), encoding="utf-8")

    payload = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    item = payload["items"][0]
    persisted = (source_dir / item["output_markdown"]).read_text(encoding="utf-8")
    assert item["output_pdf"] == "result.pdf"
    assert item["output_markdown"] == "result.md"
    assert item["summary"] == "Persisted summary"
    assert persisted.startswith(f"# Abstract\n\n{item['summary']}\n\n---\n\n")


def test_apply_rejects_existing_outputs_unless_overwrite_enabled(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    pdf_doc = {
        "source_file_name": "collision.pdf",
        "file_type": "pdf",
        "page_count": 1,
        "date_of_process": "2026-07-14T08:21:54.244888+00:00",
        "summary": "New summary",
        "markdown_file": "collision-source.md",
        "status": "ok",
    }
    (source_dir / "collision.pdf").write_bytes(b"%PDF-1.4")
    (source_dir / "collision-source.md").write_text("New body", encoding="utf-8")
    (source_dir / "collision.md").write_text("old", encoding="utf-8")
    (source_dir / "batch_mrg.json").write_text(json.dumps({"documents": [pdf_doc]}), encoding="utf-8")

    with pytest.raises(apply_mod.ApplyError) as exc:
        apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert exc.value.error_code == "output_collision"

    payload = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir, overwrite=True))
    assert payload["items"][0]["status"] == "ok"
    assert (source_dir / "collision.md").read_text(encoding="utf-8").startswith("# Abstract\n\nNew summary\n\n---\n\n")


def test_apply_rejects_existing_result_file_without_overwrite(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    (source_dir / "batch_mrg.json").write_text(json.dumps({"documents": []}), encoding="utf-8")
    (source_dir / "batch_mrg_result.json").write_text("{}", encoding="utf-8")

    with pytest.raises(apply_mod.ApplyError) as exc:
        apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert exc.value.error_code == "output_collision"


def test_apply_rejects_duplicate_planned_outputs_before_partial_writes(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    first = {
        "source_file_name": "same.pdf",
        "file_type": "pdf",
        "page_count": 1,
        "date_of_process": "2026-07-14T08:21:54.244888+00:00",
        "summary": "one",
        "markdown_file": "same-a.md",
        "status": "ok",
    }
    second = {**first, "summary": "two", "markdown_file": "same-b.md"}
    (source_dir / "same.pdf").write_bytes(b"%PDF-1.4")
    (source_dir / "same-a.md").write_text("A", encoding="utf-8")
    (source_dir / "same-b.md").write_text("B", encoding="utf-8")
    (source_dir / "batch_mrg.json").write_text(json.dumps({"documents": [first, second]}), encoding="utf-8")

    with pytest.raises(apply_mod.ApplyError) as exc:
        apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir, overwrite=True))

    assert exc.value.error_code == "output_cardinality_invalid"
    assert not (source_dir / "same.md").exists()


def test_apply_preserves_mixed_pdf_group_order(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    page_a = _write_image_and_markdown(source_dir, "page-a", "Page A")
    page_b = _write_image_and_markdown(source_dir, "page-b", "Page B")
    pdf_doc = {
        "source_file_name": "report.pdf",
        "file_type": "pdf",
        "page_count": 3,
        "date_of_process": "2026-07-14T08:21:54.244888+00:00",
        "summary": "report",
        "markdown_file": "report.md",
        "status": "ok",
    }
    (source_dir / "report.pdf").write_bytes(b"%PDF-1.4")
    (source_dir / "report.md").write_text("Report", encoding="utf-8")
    (source_dir / "batch_mrg.json").write_text(
        json.dumps({"documents": [pdf_doc, {"documents": [page_a]}, {"documents": [page_b]}]}, indent=2),
        encoding="utf-8",
    )

    payload = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert [item["item_type"] for item in payload["items"]] == ["pdf", "group", "group"]
    assert payload["items"][0]["document"] == pdf_doc
    assert payload["items"][1]["documents"] == [page_a]
    assert payload["items"][2]["documents"] == [page_b]


def test_apply_reports_empty_group_image_failure(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    (source_dir / "batch_mrg.json").write_text(json.dumps({"documents": [{"documents": []}]}), encoding="utf-8")

    payload = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert payload["items"] == [
        {
            "item_index": 1,
            "item_type": "group",
            "status": "failed",
            "error_code": "group_image_empty",
            "message": "Cannot merge an empty image group",
            "documents": [],
        }
    ]


@pytest.mark.parametrize(
    ("plan_payload", "expected_code"),
    (
        ("[]", "plan_invalid_shape"),
        (json.dumps({"documents": "not-a-list"}), "plan_documents_invalid"),
    ),
)
def test_apply_rejects_invalid_plan_payloads(tmp_path: Path, plan_payload: str, expected_code: str) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    (source_dir / "batch_mrg.json").write_text(plan_payload, encoding="utf-8")

    with pytest.raises(apply_mod.ApplyError) as exc:
        apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert exc.value.error_code == expected_code


def test_apply_accepts_null_documents_as_empty_plan(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    (source_dir / "batch_mrg.json").write_text(json.dumps({"documents": None}), encoding="utf-8")

    payload = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert payload == {"items": []}
    assert json.loads((source_dir / "batch_mrg_result.json").read_text(encoding="utf-8")) == payload


def test_apply_reports_missing_group_markdown_field(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    (source_dir / "batch_mrg.json").write_text(
        json.dumps({"documents": [{"documents": [{"source_file_name": "scan.jpg"}]}]}),
        encoding="utf-8",
    )

    payload = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert payload["items"][0]["status"] == "failed"
    assert payload["items"][0]["error_code"] == "group_markdown_missing"


def test_apply_reports_missing_group_image_field(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    (source_dir / "page.md").write_text("page", encoding="utf-8")
    (source_dir / "batch_mrg.json").write_text(
        json.dumps({"documents": [{"documents": [{"markdown_file": "page.md"}]}]}),
        encoding="utf-8",
    )

    payload = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert payload["items"][0]["status"] == "failed"
    assert payload["items"][0]["error_code"] == "group_image_missing"


def test_apply_reports_unreadable_group_image(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()
    (source_dir / "page.md").write_text("page", encoding="utf-8")
    (source_dir / "page.jpg").write_text("not an image", encoding="utf-8")
    (source_dir / "batch_mrg.json").write_text(
        json.dumps({"documents": [{"documents": [{"source_file_name": "page.jpg", "markdown_file": "page.md"}]}]}),
        encoding="utf-8",
    )

    payload = apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert payload["items"][0]["status"] == "failed"
    assert payload["items"][0]["error_code"] == "group_image_read_failed"


def test_apply_raises_for_missing_plan_file(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()

    with pytest.raises(apply_mod.ApplyError) as exc:
        apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert exc.value.error_code == "plan_file_not_found"
