from pathlib import Path

from common.config import (
    AppConfig,
    ImageSettings,
    LlamaModelSettings,
    PathSettings,
    PromptSettings,
    RuntimeSettings,
)

from common.config_dump import format_config_dump


def test_format_config_dump_contains_all_sections_and_fields() -> None:
    config = AppConfig(
        paths=PathSettings(
            source_dir=Path("C:/docs/source"),
            output_dir=Path("C:/docs/output"),
            temp_dir=Path("C:/docs/output/temp"),
        ),
        prompts=PromptSettings(
            summary_prompt_path=Path("C:/docs/prompts/summary.md"),
            summary_prompt_text="first line\nsecond line\nthird line",
        ),
        ocr_model=LlamaModelSettings(
            endpoint_url="http://localhost:11434",
            model_name="ocr-model",
            request_timeout_seconds=45.5,
            request_max_retries=3,
        ),
        language_model=LlamaModelSettings(
            endpoint_url="http://localhost:11435",
            model_name="lang-model",
            request_timeout_seconds=90.0,
            request_max_retries=4,
        ),
        image=ImageSettings(
            max_longest_edge_px=1540,
            token_threshold=16000,
        ),
        runtime=RuntimeSettings(
            dry_run=True,
            overwrite=False,
        ),
    )

    rendered = format_config_dump(config)

    assert "=== md-gen startup config dump ===" in rendered
    assert "[paths]" in rendered
    assert "source_dir=C:\\docs\\source" in rendered
    assert "output_dir=C:\\docs\\output" in rendered
    assert "temp_dir=C:\\docs\\output\\temp" in rendered

    assert "[prompts]" in rendered
    assert "summary_prompt_path=C:\\docs\\prompts\\summary.md" in rendered
    assert "summary_prompt_text:" in rendered

    assert "[ocr_model]" in rendered
    assert "endpoint_url=http://localhost:11434" in rendered
    assert "model_name=ocr-model" in rendered
    assert "request_timeout_seconds=45.5" in rendered
    assert "request_max_retries=3" in rendered

    assert "[language_model]" in rendered
    assert "endpoint_url=http://localhost:11435" in rendered
    assert "model_name=lang-model" in rendered
    assert "request_timeout_seconds=90.0" in rendered
    assert "request_max_retries=4" in rendered

    assert "[image]" in rendered
    assert "max_longest_edge_px=1540" in rendered
    assert "token_threshold=16000" in rendered

    assert "[runtime]" in rendered
    assert "dry_run=True" in rendered
    assert "overwrite=False" in rendered
    assert "=== end startup config dump ===" in rendered


def test_format_config_dump_preserves_multiline_prompt_text_verbatim() -> None:
    prompt_text = "line 1\n\n  indented line 3\nline 4"
    config = AppConfig(
        paths=PathSettings(
            source_dir=Path("C:/source"),
            output_dir=Path("C:/output"),
            temp_dir=Path("C:/output/temp"),
        ),
        prompts=PromptSettings(
            summary_prompt_path=None,
            summary_prompt_text=prompt_text,
        ),
        ocr_model=LlamaModelSettings(
            endpoint_url="http://ocr",
            model_name="ocr",
            request_timeout_seconds=12.0,
            request_max_retries=2,
        ),
        language_model=LlamaModelSettings(
            endpoint_url="http://lang",
            model_name="lang",
            request_timeout_seconds=15.0,
            request_max_retries=2,
        ),
        image=ImageSettings(
            max_longest_edge_px=1200,
            token_threshold=14000,
        ),
        runtime=RuntimeSettings(
            dry_run=False,
            overwrite=True,
        ),
    )

    rendered = format_config_dump(config)

    assert f"summary_prompt_text:\n{prompt_text}\n\n[ocr_model]" in rendered