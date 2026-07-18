import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image

from common.config import AppConfig, ImageSettings, LlamaModelSettings, MdGenSettings, MdMrgSettings, PathSettings, PromptSettings, RuntimeSettings
from md_gen.discovery import FileItem
from md_gen.page_processor import process_file
from md_gen.progress import GenerationProgressContext, GenerationProgressEvent


def _make_config(output_dir: Path, *, overwrite: bool = False) -> AppConfig:
    return AppConfig(
        paths=PathSettings(
            source_dir=output_dir.parent / "in",
            output_dir=output_dir,
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
        runtime=RuntimeSettings(dry_run=False, overwrite=overwrite),
    )


def _make_image(size: tuple[int, int] = (100, 100)) -> Image.Image:
    return Image.new("RGB", size, color=(255, 255, 255))


def test_process_file_handles_single_image(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    config = _make_config(output_dir)
    source_path = tmp_path / "scan.png"
    source_path.write_bytes(b"image")
    file_item = FileItem(source_path=source_path, source_type="image", order_index=0, ordering_key=("scan.png",))

    fake_image = _make_image()

    with (
        patch("md_gen.page_processor.rasterizer") as mock_rasterizer,
        patch("md_gen.page_processor.ocr_processor") as mock_ocr,
        patch("md_gen.page_processor.summarize") as mock_summarize,
    ):
        mock_rasterizer.get_pdf_page_count = MagicMock()
        mock_rasterizer.rasterize_page.return_value = fake_image
        mock_ocr.extract_markdown.return_value = "# Image markdown"
        mock_summarize.summarize_page.return_value = "image summary"
        mock_summarize.summarize_document.return_value = "image summary"

        result = process_file(config, file_item)

    assert result["source_file_name"] == "scan.png"
    assert result["file_type"] == "image"
    assert result["page_count"] == 1
    assert result["summary"] == "image summary"
    assert result["markdown_file"] == "scan.md"
    assert result["status"] == "ok"

    output_path = output_dir / "scan.md"
    assert output_path.read_text(encoding="utf-8") == "# Image markdown\n"
    mock_rasterizer.get_pdf_page_count.assert_not_called()
    mock_rasterizer.rasterize_page.assert_called_once_with(source_path, max_edge_size=1540, page_number=None)


def test_process_file_handles_multi_page_pdf(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    config = _make_config(output_dir)
    source_path = tmp_path / "doc.pdf"
    source_path.write_bytes(b"pdf")
    file_item = FileItem(source_path=source_path, source_type="pdf", order_index=0, ordering_key=("doc.pdf",))

    fake_images = [_make_image(), _make_image()]

    with (
        patch("md_gen.page_processor.rasterizer") as mock_rasterizer,
        patch("md_gen.page_processor.ocr_processor") as mock_ocr,
        patch("md_gen.page_processor.summarize") as mock_summarize,
    ):
        mock_rasterizer.get_pdf_page_count.return_value = 2
        mock_rasterizer.rasterize_page.side_effect = fake_images
        mock_ocr.extract_markdown.side_effect = ["# Page 1", "# Page 2"]
        mock_summarize.summarize_page.side_effect = ["summary 1", "summary 2"]
        mock_summarize.summarize_document.return_value = "combined summary"

        result = process_file(config, file_item)

    assert result["source_file_name"] == "doc.pdf"
    assert result["file_type"] == "pdf"
    assert result["page_count"] == 2
    assert result["summary"] == "combined summary"
    assert result["markdown_file"] == "doc.md"
    assert result["status"] == "ok"

    output_path = output_dir / "doc.md"
    assert output_path.read_text(encoding="utf-8") == "# Page 1\n\n# Page 2\n"
    assert mock_rasterizer.rasterize_page.call_count == 2


def test_process_file_emits_page_progress_for_pdf(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    config = _make_config(output_dir)
    source_path = tmp_path / "doc.pdf"
    source_path.write_bytes(b"pdf")
    file_item = FileItem(source_path=source_path, source_type="pdf", order_index=0, ordering_key=("doc.pdf",))
    events: list[GenerationProgressEvent] = []

    with (
        patch("md_gen.page_processor.rasterizer") as mock_rasterizer,
        patch("md_gen.page_processor.ocr_processor") as mock_ocr,
        patch("md_gen.page_processor.summarize") as mock_summarize,
    ):
        mock_rasterizer.get_pdf_page_count.return_value = 2
        mock_rasterizer.rasterize_page.side_effect = [_make_image(), _make_image()]
        mock_ocr.extract_markdown.side_effect = ["# Page 1", "# Page 2"]
        mock_summarize.summarize_page.side_effect = ["summary 1", "summary 2"]
        mock_summarize.summarize_document.return_value = "combined summary"

        process_file(
            config,
            file_item,
            progress_callback=events.append,
            progress_context=GenerationProgressContext(total_jobs=2),
        )

    assert [event.kind for event in events] == [
        "ocr_item_start",
        "ocr_item_complete",
        "ocr_item_start",
        "ocr_item_complete",
    ]
    assert [event.page_number for event in events] == [1, 1, 2, 2]
    assert [event.completed_jobs for event in events] == [0, 1, 1, 2]
    assert events[-1].markdown_count == 2


def test_process_file_writes_partial_markdown_on_failure(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    config = _make_config(output_dir)
    source_path = tmp_path / "doc.pdf"
    source_path.write_bytes(b"pdf")
    file_item = FileItem(source_path=source_path, source_type="pdf", order_index=0, ordering_key=("doc.pdf",))

    fake_image = _make_image()

    with (
        patch("md_gen.page_processor.rasterizer") as mock_rasterizer,
        patch("md_gen.page_processor.ocr_processor") as mock_ocr,
        patch("md_gen.page_processor.summarize") as mock_summarize,
    ):
        mock_rasterizer.get_pdf_page_count.return_value = 2
        mock_rasterizer.rasterize_page.side_effect = [fake_image, RuntimeError("render failed")]
        mock_ocr.extract_markdown.return_value = "# Page 1"
        mock_summarize.summarize_page.return_value = "summary 1"

        result = process_file(config, file_item)

    assert result["status"] == "failed"
    assert result["summary"] == ""

    output_path = output_dir / "doc.md"
    assert output_path.read_text(encoding="utf-8") == "# Page 1\n"


def test_process_file_respects_overwrite_flag(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    config = _make_config(output_dir, overwrite=False)
    source_path = tmp_path / "scan.png"
    source_path.write_bytes(b"image")
    file_item = FileItem(source_path=source_path, source_type="image", order_index=0, ordering_key=("scan.png",))

    existing_path = output_dir / "scan.md"
    existing_path.write_text("existing\n", encoding="utf-8")

    fake_image = _make_image()

    with (
        patch("md_gen.page_processor.rasterizer") as mock_rasterizer,
        patch("md_gen.page_processor.ocr_processor") as mock_ocr,
        patch("md_gen.page_processor.summarize") as mock_summarize,
    ):
        mock_rasterizer.rasterize_page.return_value = fake_image
        mock_ocr.extract_markdown.return_value = "# New"
        mock_summarize.summarize_page.return_value = "summary"
        mock_summarize.summarize_document.return_value = "summary"

        result = process_file(config, file_item)

    assert result["status"] == "ok"
    assert existing_path.read_text(encoding="utf-8") == "existing\n"


def test_process_file_overwrites_when_flag_set(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    config = _make_config(output_dir, overwrite=True)
    source_path = tmp_path / "scan.png"
    source_path.write_bytes(b"image")
    file_item = FileItem(source_path=source_path, source_type="image", order_index=0, ordering_key=("scan.png",))

    existing_path = output_dir / "scan.md"
    existing_path.write_text("existing\n", encoding="utf-8")

    fake_image = _make_image()

    with (
        patch("md_gen.page_processor.rasterizer") as mock_rasterizer,
        patch("md_gen.page_processor.ocr_processor") as mock_ocr,
        patch("md_gen.page_processor.summarize") as mock_summarize,
    ):
        mock_rasterizer.rasterize_page.return_value = fake_image
        mock_ocr.extract_markdown.return_value = "# New"
        mock_summarize.summarize_page.return_value = "summary"
        mock_summarize.summarize_document.return_value = "summary"

        result = process_file(config, file_item)

    assert result["status"] == "ok"
    assert existing_path.read_text(encoding="utf-8") == "# New\n"
