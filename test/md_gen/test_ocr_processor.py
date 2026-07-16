from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image

from md_gen.config import AppConfig, ImageSettings, LlamaModelSettings, PathSettings, PromptSettings, RuntimeSettings
from md_gen.ocr_processor import extract_markdown


def _make_config() -> AppConfig:
    return AppConfig(
        paths=PathSettings(
            source_dir=Path("/in"),
            output_dir=Path("/out"),
            temp_dir=Path("/out/temp"),
        ),
        prompts=PromptSettings(summary_prompt_path=None, summary_prompt_text="summarize"),
        ocr_model=LlamaModelSettings(
            endpoint_url="http://127.0.0.1:8080/v1",
            model_name="lightonocr-2",
            request_timeout_seconds=120.0,
            request_max_retries=2,
        ),
        language_model=LlamaModelSettings(
            endpoint_url="http://127.0.0.1:8081/v1",
            model_name="qwen3-1.7b",
            request_timeout_seconds=120.0,
            request_max_retries=2,
        ),
        image=ImageSettings(max_longest_edge_px=1540, token_threshold=4096),
        runtime=RuntimeSettings(dry_run=False, overwrite=False),
    )


def test_extract_markdown_returns_response_text_and_performs_no_file_io(tmp_path: Path) -> None:
    config = _make_config()
    image = Image.new("RGB", (32, 32), color=(255, 255, 255))

    mock_response = MagicMock()
    mock_response.markdown_text = "# OCR Output\n\nHello"

    with patch("md_gen.ocr_processor.LlamaOcrGateway") as mock_gateway_cls:
        mock_gateway = MagicMock()
        mock_gateway.__enter__ = MagicMock(return_value=mock_gateway)
        mock_gateway.__exit__ = MagicMock(return_value=None)
        mock_gateway.send_ocr_request_from_image.return_value = mock_response
        mock_gateway_cls.return_value = mock_gateway

        result = extract_markdown(config, image)

    assert result == "# OCR Output\n\nHello"
    mock_gateway.send_ocr_request_from_image.assert_called_once_with(image)
    image.close()
