from argparse import Namespace
from pathlib import Path

from md_gen.config import DEFAULT_SUMMARY_PROMPT_FILE, ConfigValidationError, build_config_from_args


def _build_args(source: Path, output: Path, summary_prompt: str | None = None) -> Namespace:
    return Namespace(
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
        dry_run=True,
        overwrite=False,
    )


def test_build_config_derives_paths_under_output_temp(tmp_path: Path) -> None:
    source_dir = tmp_path / "incoming"
    source_dir.mkdir()
    output_dir = tmp_path / "out"

    config = build_config_from_args(_build_args(source_dir, output_dir))

    assert config.paths.source_dir == source_dir.resolve()
    assert config.paths.output_dir == output_dir.resolve()
    assert config.paths.temp_dir == (output_dir / "temp").resolve()
    assert config.paths.im_temp_dir == (output_dir / "temp" / "images").resolve()
    assert config.paths.md_temp_dir == (output_dir / "temp" / "markdown").resolve()
    assert config.paths.metadata_temp_dir == (output_dir / "temp" / "metadata").resolve()
    assert config.prompts.summary_prompt_default_path == DEFAULT_SUMMARY_PROMPT_FILE


def test_build_config_creates_output_dir_if_missing(tmp_path: Path) -> None:
    source_dir = tmp_path / "incoming"
    source_dir.mkdir()
    output_dir = tmp_path / "does-not-exist"

    assert output_dir.exists() is False
    build_config_from_args(_build_args(source_dir, output_dir))
    assert output_dir.is_dir()


def test_build_config_rejects_non_directory_source(tmp_path: Path) -> None:
    source_file = tmp_path / "one.png"
    source_file.write_bytes(b"x")

    try:
        build_config_from_args(_build_args(source_file, tmp_path / "out"))
    except ConfigValidationError as exc:
        assert exc.error_code == "invalid_source_directory"
    else:
        raise AssertionError("Expected ConfigValidationError for non-directory --source")
