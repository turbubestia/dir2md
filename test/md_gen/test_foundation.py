from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from common.gateway import OcrResponse
from md_gen.config import BUILTIN_SUMMARY_PROMPT, build_config_from_args
from md_gen.foundation import SummaryAttempt, run_foundation_bootstrap


def _make_image(path: Path, size: tuple[int, int] = (200, 150)) -> None:
    image = Image.new("RGB", size, color=(240, 240, 240))
    image.save(path)
    image.close()


def _build_args(source: Path, output: Path, *, dry_run: bool, overwrite: bool, summary_prompt: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        source=str(source),
        output=str(output),
        summary_prompt=summary_prompt,
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
        dry_run=dry_run,
        overwrite=overwrite,
    )


def test_run_foundation_dry_run_writes_under_output_temp_only(tmp_path: Path, capsys) -> None:
    source_dir = tmp_path / "input"
    source_dir.mkdir()
    output_dir = tmp_path / "out"

    _make_image(source_dir / "invoice.png")

    config = build_config_from_args(_build_args(source_dir, output_dir, dry_run=True, overwrite=False))
    exit_code = run_foundation_bootstrap(config)

    assert exit_code == 0
    assert config.paths.output_dir.is_dir()
    assert config.paths.temp_dir.is_dir()

    generated_images = list(config.paths.temp_dir.glob("*.png"))
    generated_markdown = list(config.paths.temp_dir.glob("*.md"))
    generated_json = list(config.paths.temp_dir.glob("*.json"))
    assert len(generated_images) == 1
    assert generated_markdown == []
    assert generated_json == []

    stdout = capsys.readouterr().out
    assert "STAGE name=execute_ocr status=skipped" in stdout
    assert "STAGE name=persist_metadata status=skipped" in stdout


def test_run_foundation_enforces_overwrite_for_markdown_and_metadata_outputs(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "input"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    source_image = source_dir / "page.png"
    _make_image(source_image)

    def fake_execute_ocr(config, resized_images):
        return tuple(
            OcrResponse(
                image_path=result.output_image_path,
                model_name=config.ocr_model.model_name,
                markdown_text="# OCR\n\ncontent",
                raw_response={},
            )
            for result in resized_images
        )

    def fake_execute_summaries(config, ocr_responses):
        return tuple(
            SummaryAttempt(
                image_path=response.image_path,
                summary_text="Short summary",
                failed=False,
                error_code=None,
            )
            for response in ocr_responses
        )

    monkeypatch.setattr("md_gen.foundation.execute_ocr", fake_execute_ocr)
    monkeypatch.setattr("md_gen.foundation.execute_summaries", fake_execute_summaries)

    first_config = build_config_from_args(_build_args(source_dir, output_dir, dry_run=False, overwrite=False))
    assert run_foundation_bootstrap(first_config) == 0
    assert len(tuple(first_config.paths.temp_dir.glob("*.md"))) == 1
    assert len(tuple(first_config.paths.temp_dir.glob("*.json"))) == 1

    second_config = build_config_from_args(_build_args(source_dir, output_dir, dry_run=False, overwrite=False))
    assert run_foundation_bootstrap(second_config) == 0
    assert len(tuple(second_config.paths.temp_dir.glob("*.md"))) == 1
    assert len(tuple(second_config.paths.temp_dir.glob("*.json"))) == 1

    third_config = build_config_from_args(_build_args(source_dir, output_dir, dry_run=False, overwrite=True))
    assert run_foundation_bootstrap(third_config) == 0
    assert len(tuple(third_config.paths.temp_dir.glob("*.md"))) == 1
    assert len(tuple(third_config.paths.temp_dir.glob("*.json"))) == 1


def test_run_foundation_returns_coded_error_for_pipeline_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    source_dir = tmp_path / "input"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    _make_image(source_dir / "page.png")

    def fail_execute_ocr(config, resized_images):
        raise RuntimeError("simulated-gateway-failure")

    monkeypatch.setattr("md_gen.foundation.execute_ocr", fail_execute_ocr)

    config = build_config_from_args(_build_args(source_dir, output_dir, dry_run=False, overwrite=False))
    exit_code = run_foundation_bootstrap(config)

    assert exit_code == 1
    stdout = capsys.readouterr().out
    assert "ERROR code=foundation_runtime_error" in stdout
    assert "simulated-gateway-failure" in stdout


# def test_load_summary_prompt_prefers_override_then_default_then_builtin(tmp_path: Path) -> None:
#     source_dir = tmp_path / "input"
#     source_dir.mkdir()
#     output_dir = tmp_path / "out"

#     override_prompt = tmp_path / "override.txt"
#     override_prompt.write_text("override prompt", encoding="utf-8")

#     config_override = build_config_from_args(
#         _build_args(source_dir, output_dir, dry_run=True, overwrite=False, summary_prompt=str(override_prompt))
#     )
#     assert config_override.prompts.summary_prompt_text == "override prompt"

#     missing_override = tmp_path / "missing.txt"
#     default_prompt = tmp_path / "default.txt"
#     default_prompt.write_text("default prompt", encoding="utf-8")

#     config_default = build_config_from_args(
#         _build_args(source_dir, output_dir, dry_run=True, overwrite=False, summary_prompt=str(missing_override))
#     )
#     from dataclasses import replace

#     config_default = replace(
#         config_default,
#         prompts=replace(config_default.prompts, summary_prompt_default_path=default_prompt),
#     )
#     assert load_summary_system_prompt(config_default) == "default prompt"

#     default_prompt.write_text("", encoding="utf-8")
#     assert load_summary_system_prompt(config_default) == BUILTIN_SUMMARY_PROMPT
