import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image

from common.config import build_config_from_args
from md_gen.foundation import run_foundation_bootstrap


def _make_image(path: Path, size: tuple[int, int] = (200, 150)) -> None:
    image = Image.new("RGB", size, color=(240, 240, 240))
    image.save(path)
    image.close()


def _build_args(source: Path, output: Path, *, overwrite: bool = False, summary_prompt: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        source=str(source),
        output=str(output),
        summary_prompt=summary_prompt,
        ocr_model_endpoint=None,
        ocr_model_name=None,
        ocr_timeout_seconds=None,
        ocr_max_retries=None,
        language_model_endpoint=None,
        language_model_name=None,
        language_timeout_seconds=None,
        language_max_retries=None,
        max_longest_edge_px=None,
        token_threshold=None,
        dry_run=False,
        overwrite=overwrite,
    )


def test_run_foundation_writes_batch_json_per_source(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "input"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    _make_image(source_dir / "invoice.png")

    with patch("md_gen.foundation.process_file") as mock_process_file:
        mock_process_file.return_value = {
            "source_file_name": "invoice.png",
            "file_type": "image",
            "page_count": 1,
            "date_of_process": "2026-01-01T00:00:00+00:00",
            "summary": "invoice summary",
            "markdown_file": "invoice.md",
            "status": "ok",
        }

        config = build_config_from_args(_build_args(source_dir, output_dir))
        exit_code = run_foundation_bootstrap(config)

    assert exit_code == 0
    batch_path = output_dir / "batch.json"
    assert batch_path.exists()
    payload = json.loads(batch_path.read_text(encoding="utf-8"))
    assert payload["documents"][0]["source_file_name"] == "invoice.png"
    mock_process_file.assert_called_once()


def test_run_foundation_continues_after_file_failure(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "input"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    _make_image(source_dir / "a.png")
    _make_image(source_dir / "b.png")

    def fake_process_file(config, file_item, **_kwargs):
        if file_item.source_path.name == "a.png":
            return {
                "source_file_name": "a.png",
                "file_type": "image",
                "page_count": 1,
                "date_of_process": "2026-01-01T00:00:00+00:00",
                "summary": "",
                "markdown_file": "a.md",
                "status": "failed",
            }
        return {
            "source_file_name": "b.png",
            "file_type": "image",
            "page_count": 1,
            "date_of_process": "2026-01-01T00:00:00+00:00",
            "summary": "summary b",
            "markdown_file": "b.md",
            "status": "ok",
        }

    monkeypatch.setattr("md_gen.foundation.process_file", fake_process_file)

    config = build_config_from_args(_build_args(source_dir, output_dir))
    exit_code = run_foundation_bootstrap(config)

    assert exit_code == 0
    batch_path = output_dir / "batch.json"
    payload = json.loads(batch_path.read_text(encoding="utf-8"))
    assert len(payload["documents"]) == 2
    assert payload["documents"][0]["status"] == "failed"
    assert payload["documents"][1]["status"] == "ok"


def test_run_foundation_returns_config_validation_error_code(tmp_path: Path) -> None:
    source_dir = tmp_path / "input"
    source_dir.mkdir()
    output_dir = tmp_path / "out"

    config = build_config_from_args(_build_args(source_dir, output_dir))

    with patch("md_gen.foundation.build_work_items") as mock_build_work_items:
        from common.config import ConfigValidationError
        mock_build_work_items.side_effect = ConfigValidationError("invalid_source_directory", "missing")
        exit_code = run_foundation_bootstrap(config)

    assert exit_code == 2


def test_run_foundation_returns_gateway_error_code(tmp_path: Path) -> None:
    source_dir = tmp_path / "input"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    _make_image(source_dir / "page.png")

    config = build_config_from_args(_build_args(source_dir, output_dir))

    with patch("md_gen.foundation.process_file") as mock_process_file:
        from common.gateway import GatewayError
        mock_process_file.side_effect = GatewayError("connection_error", "down")
        exit_code = run_foundation_bootstrap(config)

    assert exit_code == 4


def test_run_foundation_returns_runtime_error_code_for_unexpected_exception(tmp_path: Path) -> None:
    source_dir = tmp_path / "input"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    _make_image(source_dir / "page.png")

    config = build_config_from_args(_build_args(source_dir, output_dir))

    with patch("md_gen.foundation.build_work_items") as mock_build_work_items:
        mock_build_work_items.side_effect = RuntimeError("unexpected")
        exit_code = run_foundation_bootstrap(config)

    assert exit_code == 1
