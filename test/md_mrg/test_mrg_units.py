import json
from pathlib import Path

from PIL import Image
import pytest

from common.config import AppConfig, ImageSettings, LlamaModelSettings, MdGenSettings, MdMrgSettings, PathSettings, PromptSettings, RuntimeSettings
from md_mrg import apply as apply_mod
from md_mrg import planner as planner_mod


def _cfg(source_dir: Path) -> AppConfig:
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
        runtime=RuntimeSettings(dry_run=False, overwrite=False),
    )


def _image_doc(stem: str) -> dict:
    return {
        "source_file_name": f"{stem}.jpg",
        "file_type": "image",
        "page_count": 1,
        "date_of_process": "2026-07-14T08:21:54.244888+00:00",
        "summary": "summary",
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

    assert (source_dir / "merger-001.md").exists()
    assert (source_dir / "merged-001.pdf").exists()
    merged_markdown = (source_dir / "merger-001.md").read_text(encoding="utf-8")
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
    assert payload["items"][1]["item_type"] == "pdf"


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
    assert (source_dir / "merged-002.pdf").exists()
    assert (source_dir / "merger-002.md").exists()


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
    assert (source_dir / "merged-001.pdf").exists()
    assert (source_dir / "merged-002.pdf").exists()


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


def test_apply_raises_for_missing_plan_file(tmp_path: Path) -> None:
    source_dir = tmp_path / "out"
    source_dir.mkdir()

    with pytest.raises(apply_mod.ApplyError) as exc:
        apply_mod.run_apply(source_dir=source_dir, cfg=_cfg(source_dir))

    assert exc.value.error_code == "plan_file_not_found"
