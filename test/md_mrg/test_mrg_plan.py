import json
from dataclasses import replace
from pathlib import Path

from PIL import Image

from md_mrg.apply import ApplyError, apply_merge_plan
from md_mrg.cli import DEFAULT_SCORE_PROMPT_FILE, _build_parser, main
from md_mrg.io import derive_metadata_dir, derive_plan_file
from md_mrg.models import PlanConfig
from md_mrg.planner import build_merge_plan, load_score_system_prompt
import md_mrg.scorers as scorers


def _write_document_metadata(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _verified_doc_payload() -> dict:
    return {
        "document_id": "doc-verified",
        "source_name": "invoice.pdf",
        "total_pages": 1,
        "is_verified_sequence": True,
        "fragments": [
            {
                "sequence_number": 1,
                "image_file": "page-1.png",
                "markdown_file": "page-1.md",
                "anchors": {
                    "first_line": "invoice",
                    "last_line": "total",
                },
                "content_fingerprint": {
                    "snippet": "invoice summary",
                    "detected_entities": [],
                },
            }
        ],
    }


def _base_plan_config(source_root: Path) -> PlanConfig:
    return PlanConfig(
        source_root=source_root,
        temp_root=source_root / "temp",
        metadata_dir=source_root / "temp" / "metadata",
        markdown_dir=source_root / "temp" / "markdown",
        image_dir=source_root / "temp" / "images",
        plan_file=source_root / "merge-plan.json",
        edge_scorer="llm",
        rolling_window=5,
        llm_endpoint_url="http://localhost:8081/v1/chat/completions",
        llm_model_name="qwen3-1.7b",
        llm_timeout_seconds=120.0,
        llm_max_retries=0,
        score_prompt_override_path=None,
        score_prompt_default_path=DEFAULT_SCORE_PROMPT_FILE,
        score_prompt_builtin_text="builtin score prompt",
        overwrite=True,
    )


def test_plan_cli_rejects_non_llm_edge_scorer() -> None:
    parser = _build_parser()
    try:
        parser.parse_args(["plan", "--source", "/tmp", "--edge-scorer", "heuristic"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Expected parser failure for non-llm edge scorer")


def test_mrg_plan_builds_deterministic_plan_in_source_root(tmp_path: Path, monkeypatch) -> None:
    source_root = tmp_path / "output"
    metadata_dir = derive_metadata_dir(source_root)
    metadata_dir.mkdir(parents=True)

    _write_document_metadata(metadata_dir / "verified.json", _verified_doc_payload())

    monkeypatch.setattr(
        "sys.argv",
        [
            "md-mrg",
            "plan",
            "--source",
            str(source_root),
            "--edge-scorer",
            "llm",
            "--overwrite",
        ],
    )

    exit_code = main()
    assert exit_code == 0

    plan_file = derive_plan_file(source_root)
    assert plan_file.exists()
    payload = json.loads(plan_file.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "2.0"
    assert payload["scorer_mode"] == "llm"
    assert payload["metadata_dir"] == str(metadata_dir)


def test_mrg_apply_uses_source_root_paths(tmp_path: Path) -> None:
    source_root = tmp_path / "output"
    markdown_dir = source_root / "temp" / "markdown"
    image_dir = source_root / "temp" / "images"
    markdown_dir.mkdir(parents=True)
    image_dir.mkdir(parents=True)

    (markdown_dir / "a.md").write_text("Page A", encoding="utf-8")
    (markdown_dir / "b.md").write_text("Page B", encoding="utf-8")
    Image.new("RGB", (200, 300), color=(255, 255, 255)).save(image_dir / "a.jpg")
    Image.new("RGB", (200, 300), color=(255, 255, 255)).save(image_dir / "b.jpg")

    plan_file = derive_plan_file(source_root)
    plan_file.write_text(
        json.dumps(
            {
                "batch_id": "batch-1",
                "generated_at_utc": "2026-07-07T00:00:00+00:00",
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

    exit_code = apply_merge_plan(source_root=source_root, overwrite=True)
    assert exit_code == 0

    merged_markdown_files = list(source_root.glob("*.md"))
    assert len(merged_markdown_files) == 1
    content = merged_markdown_files[0].read_text(encoding="utf-8")
    assert "Page A" in content
    assert "\n\n---\n\n" in content
    assert "Page B" in content
    assert len(tuple(source_root.glob("*.pdf"))) == 1


def test_apply_returns_coded_error_when_plan_missing(tmp_path: Path) -> None:
    source_root = tmp_path / "output"
    source_root.mkdir()
    (source_root / "temp" / "markdown").mkdir(parents=True)
    (source_root / "temp" / "images").mkdir(parents=True)

    try:
        apply_merge_plan(source_root=source_root)
    except ApplyError as exc:
        assert exc.error_code == "plan_file_not_found"
    else:
        raise AssertionError("Expected ApplyError for missing deterministic plan file")


def test_load_score_prompt_uses_override_default_builtin(tmp_path: Path) -> None:
    source_root = tmp_path / "output"
    config = _base_plan_config(source_root)

    override_file = tmp_path / "override.txt"
    override_file.write_text("override prompt", encoding="utf-8")
    override_config = replace(config, score_prompt_override_path=override_file)
    assert load_score_system_prompt(override_config) == "override prompt"

    default_file = tmp_path / "default.txt"
    default_file.write_text("default prompt", encoding="utf-8")
    default_config = replace(
        config,
        score_prompt_override_path=tmp_path / "missing.txt",
        score_prompt_default_path=default_file,
    )
    assert load_score_system_prompt(default_config) == "default prompt"

    default_file.write_text("", encoding="utf-8")
    assert load_score_system_prompt(default_config) == "builtin score prompt"


def test_heuristic_scorer_is_removed() -> None:
    assert hasattr(scorers, "LlmEdgeScorer")
    assert hasattr(scorers, "HeuristicEdgeScorer") is False


def test_build_merge_plan_writes_same_deterministic_filename(tmp_path: Path) -> None:
    source_root = tmp_path / "output"
    metadata_dir = derive_metadata_dir(source_root)
    metadata_dir.mkdir(parents=True)
    _write_document_metadata(metadata_dir / "verified.json", _verified_doc_payload())

    config = _base_plan_config(source_root)
    first = build_merge_plan(config)
    second = build_merge_plan(config)

    assert first.output_path == second.output_path
    assert first.output_path.name == "merge-plan.json"
