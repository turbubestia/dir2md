from argparse import Namespace
from pathlib import Path

from PIL import Image

from md_gen.config import build_config_from_args
from md_gen.foundation import run_foundation_bootstrap
from md_gen.gateway import OcrResponse


def _make_image(path: Path, size: tuple[int, int] = (200, 150)) -> None:
    image = Image.new("RGB", size, color=(240, 240, 240))
    image.save(path)
    image.close()


def _build_args(source: Path, *, dry_run: bool, overwrite: bool) -> Namespace:
    return Namespace(
        source=[str(source)],
        source_list_file=[],
        output_dir=None,
        im_temp_dir=None,
        md_temp_dir=None,
        log_file=None,
        model_endpoint_url="http://127.0.0.1:8080/v1/chat/completions",
        model_name="lightonocr-2",
        request_timeout_seconds=120.0,
        request_max_retries=2,
        max_longest_edge_px=1540,
        token_threshold=16000,
        dry_run=dry_run,
        overwrite=overwrite,
    )


def test_run_foundation_dry_run_writes_temp_artifacts_and_skips_markdown(tmp_path: Path) -> None:
    source_dir = tmp_path / "input"
    source_dir.mkdir()
    source_image = source_dir / "invoice.png"
    _make_image(source_image)

    config = build_config_from_args(_build_args(source_dir, dry_run=True, overwrite=False))

    exit_code = run_foundation_bootstrap(config)

    assert exit_code == 0
    assert config.paths.im_temp_dir.is_dir()
    assert config.paths.md_temp_dir.is_dir()
    assert config.paths.log_file.exists()
    assert config.paths.output_dir.exists() is False

    generated_images = list(config.paths.im_temp_dir.glob("*.png"))
    generated_markdown = list(config.paths.md_temp_dir.glob("*.md"))
    assert len(generated_images) == 1
    assert generated_markdown == []

    log_content = config.paths.log_file.read_text(encoding="utf-8")
    assert "STAGE name=execute_ocr status=skipped" in log_content
    assert "STAGE name=persist_markdown status=skipped" in log_content
    assert "RUN_SUMMARY status=ok" in log_content


def test_run_foundation_enforces_overwrite_for_markdown_outputs(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "input"
    source_dir.mkdir()
    source_image = source_dir / "page.png"
    _make_image(source_image)

    def fake_execute_ocr(config, resized_images):
        return tuple(
            OcrResponse(
                image_path=result.output_image_path,
                model_name=config.model.model_name,
                markdown_text="# OCR\n\ncontent",
                raw_response={},
            )
            for result in resized_images
        )

    monkeypatch.setattr("md_gen.foundation.execute_ocr", fake_execute_ocr)

    first_config = build_config_from_args(_build_args(source_dir, dry_run=False, overwrite=False))
    assert run_foundation_bootstrap(first_config) == 0
    assert len(tuple(first_config.paths.md_temp_dir.glob("*.md"))) == 1

    second_config = build_config_from_args(_build_args(source_dir, dry_run=False, overwrite=False))
    try:
        run_foundation_bootstrap(second_config)
    except FileExistsError:
        pass
    else:
        raise AssertionError("Expected FileExistsError when overwrite is disabled")

    third_config = build_config_from_args(_build_args(source_dir, dry_run=False, overwrite=True))
    assert run_foundation_bootstrap(third_config) == 0
    assert len(tuple(third_config.paths.md_temp_dir.glob("*.md"))) == 1


def test_run_foundation_logs_failure_summary_on_pipeline_error(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "input"
    source_dir.mkdir()
    source_image = source_dir / "page.png"
    _make_image(source_image)

    def fail_execute_ocr(config, resized_images):
        raise RuntimeError("simulated-gateway-failure")

    monkeypatch.setattr("md_gen.foundation.execute_ocr", fail_execute_ocr)

    config = build_config_from_args(_build_args(source_dir, dry_run=False, overwrite=False))

    try:
        run_foundation_bootstrap(config)
    except RuntimeError as exc:
        assert "simulated-gateway-failure" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError from mocked OCR failure")

    log_content = config.paths.log_file.read_text(encoding="utf-8")
    assert "RUN_SUMMARY status=failed" in log_content
    assert "error=RuntimeError" in log_content
