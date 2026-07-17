from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from common.config import AppConfig, ImageSettings, LlamaModelSettings, MdGenSettings, MdMrgSettings, PathSettings, PromptSettings, RuntimeSettings
from md_gen.summarize import summarize_document, summarize_page


def _make_config() -> AppConfig:
    return AppConfig(
        paths=PathSettings(
            source_dir=Path("/in"),
            output_dir=Path("/out"),
        ),
        md_gen=MdGenSettings(
            prompts=PromptSettings(summary_prompt_path=None, summary_prompt_text="summarize"),
            image=ImageSettings(max_longest_edge_px=1540, token_threshold=4096),
        ),
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
        md_mrg=MdMrgSettings(score=PromptSettings(summary_prompt_path=Path("/score"), summary_prompt_text="score")),
        runtime=RuntimeSettings(dry_run=False, overwrite=False),
    )


def test_summarize_page_returns_empty_for_empty_input() -> None:
    config = _make_config()

    with patch("md_gen.summarize.LlamaLanguageGateway") as mock_gateway_cls:
        assert summarize_page(config, "   ") == ""
        mock_gateway_cls.assert_not_called()


def test_summarize_page_sends_text_request_and_returns_text() -> None:
    config = _make_config()

    mock_response = MagicMock()
    mock_response.text = "Invoice summary"

    with patch("md_gen.summarize.LlamaLanguageGateway") as mock_gateway_cls:
        mock_gateway = MagicMock()
        mock_gateway.__enter__ = MagicMock(return_value=mock_gateway)
        mock_gateway.__exit__ = MagicMock(return_value=None)
        mock_gateway.send_text_request.return_value = mock_response
        mock_gateway_cls.return_value = mock_gateway

        result = summarize_page(config, "# Invoice\n\nTotal: $100")

    assert result == "Invoice summary"


def test_summarize_document_returns_empty_for_empty_summaries() -> None:
    config = _make_config()

    with patch("md_gen.summarize.summarize_page") as mock_summarize_page:
        assert summarize_document(config, ["", "   "]) == ""
        mock_summarize_page.assert_not_called()


def test_summarize_document_reuses_single_page_summary() -> None:
    config = _make_config()

    with patch("md_gen.summarize.summarize_page") as mock_summarize_page:
        assert summarize_document(config, ["only summary"]) == "only summary"
        mock_summarize_page.assert_not_called()


def test_summarize_document_combines_multiple_summaries() -> None:
    config = _make_config()

    with patch("md_gen.summarize.summarize_page") as mock_summarize_page:
        mock_summarize_page.return_value = "combined summary"
        result = summarize_document(config, ["page one", "page two"])

    assert result == "combined summary"
    mock_summarize_page.assert_called_once_with(config, "page one\n\npage two")
