from pathlib import Path

from md_gen.gateway import OcrResponse
from md_gen.markdown_writer import persist_ocr_markdown
from md_gen.rasterizer import PdfPageRaster
from md_gen.resizer import ImageResizeResult
from md_gen.token_budget import ImageTokenBudgetReport


def _resize_result(source: Path, output: Path, width: int, height: int) -> ImageResizeResult:
    return ImageResizeResult(
        source_image_path=source,
        output_image_path=output,
        original_width=width,
        original_height=height,
        resized_width=width,
        resized_height=height,
        was_resized=False,
        max_longest_edge_px=1540,
        is_valid_for_ocr=True,
    )


def _token_report(image_path: Path, tokens: int) -> ImageTokenBudgetReport:
    return ImageTokenBudgetReport(
        image_path=image_path.as_posix(),
        width=100,
        height=100,
        estimated_tokens=tokens,
        token_threshold=16000,
        warning_threshold_tokens=14400,
        status="ok",
        message="ok",
    )


def test_persist_ocr_markdown_writes_metadata_and_traceability_for_image_source(tmp_path: Path) -> None:
    source_image = tmp_path / "scan.png"
    source_image.write_bytes(b"x")
    processed_image = tmp_path / "im-temp" / "scan-proc.png"
    processed_image.parent.mkdir(parents=True)
    processed_image.write_bytes(b"x")

    resized = _resize_result(source=source_image, output=processed_image, width=1000, height=600)
    report = _token_report(processed_image, tokens=585)
    response = OcrResponse(
        image_path=processed_image,
        model_name="lightonocr-2",
        markdown_text="# Title\n\nBody",
        raw_response={},
    )

    records = persist_ocr_markdown(
        ocr_responses=(response,),
        pdf_pages=tuple(),
        resized_images=(resized,),
        token_reports=(report,),
        md_temp_dir=tmp_path / "md-temp",
        model_name="lightonocr-2",
        overwrite=False,
    )

    assert len(records) == 1
    output_path = records[0].output_markdown_path
    content = output_path.read_text(encoding="utf-8")
    assert "source_type: image" in content
    assert f"source_file_path: {source_image.as_posix()}" in content
    assert "estimated_vision_tokens: 585" in content
    assert "# Title" in content


def test_persist_ocr_markdown_sets_pdf_page_metadata(tmp_path: Path) -> None:
    source_pdf = tmp_path / "doc.pdf"
    source_pdf.write_bytes(b"pdf")
    page_image = tmp_path / "im-temp" / "doc-page.png"
    page_image.parent.mkdir(parents=True)
    page_image.write_bytes(b"x")

    pdf_page = PdfPageRaster(
        source_pdf_path=source_pdf,
        source_order_index=0,
        source_ordering_key=source_pdf.as_posix(),
        page_index=1,
        page_number=2,
        total_pages=3,
        image_path=page_image,
        image_width=1200,
        image_height=900,
    )
    resized = _resize_result(source=page_image, output=page_image, width=1200, height=900)
    report = _token_report(page_image, tokens=1054)
    response = OcrResponse(
        image_path=page_image,
        model_name="lightonocr-2",
        markdown_text="content",
        raw_response={},
    )

    records = persist_ocr_markdown(
        ocr_responses=(response,),
        pdf_pages=(pdf_page,),
        resized_images=(resized,),
        token_reports=(report,),
        md_temp_dir=tmp_path / "md-temp",
        model_name="lightonocr-2",
        overwrite=False,
    )

    content = records[0].output_markdown_path.read_text(encoding="utf-8")
    assert "source_type: pdf_page" in content
    assert "source_page_index: 1" in content
    assert f"source_file_path: {source_pdf.as_posix()}" in content
