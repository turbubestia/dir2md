from argparse import Namespace
from pathlib import Path

from md_gen.config import build_config_from_args
from md_gen.discovery import build_work_items


def _build_args(source: Path, output: Path) -> Namespace:
    return Namespace(
        source=str(source),
        output=str(output),
        summary_prompt=None,
        ocr_model_endpoint_url="http://127.0.0.1:8080/v1/chat/completions",
        ocr_model_name="lightonocr-2",
        ocr_request_timeout_seconds=120.0,
        ocr_request_max_retries=2,
        language_model_endpoint_url="http://localhost:8081/v1/chat/completions",
        language_model_name="qwen3-1.7b",
        language_request_timeout_seconds=120.0,
        language_request_max_retries=2,
        max_longest_edge_px=1540,
        token_threshold=16000,
        dry_run=True,
        overwrite=False,
    )


def test_discovery_is_non_recursive_and_applies_allow_list(tmp_path: Path, capsys) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    output_dir = tmp_path / "output"

    (source_dir / "doc.pdf").touch()
    (source_dir / "scan.jpg").touch()
    (source_dir / "legacy.jpge").touch()
    (source_dir / "notes.txt").touch()

    nested_dir = source_dir / "nested"
    nested_dir.mkdir()
    (nested_dir / "nested.png").touch()

    config = build_config_from_args(_build_args(source_dir, output_dir))
    work_items = build_work_items(config)

    assert tuple(item.source_path.name for item in work_items) == ("doc.pdf", "legacy.jpge", "scan.jpg")
    assert tuple(item.source_type for item in work_items) == ("pdf", "image", "image")

    output = capsys.readouterr().out
    assert "DISCOVERY status=consumed" in output
    assert "DISCOVERY status=skipped" in output
    assert "notes.txt" in output
    assert "nested" in output


def test_discovery_skips_jpeg_extension_in_phase_one(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    output_dir = tmp_path / "output"

    (source_dir / "photo.jpeg").touch()

    config = build_config_from_args(_build_args(source_dir, output_dir))
    work_items = build_work_items(config)

    assert work_items == tuple()
