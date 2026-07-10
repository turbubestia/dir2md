from pathlib import Path

from PIL import Image

from md_gen.discovery import WorkItem
from md_gen.rasterizer import (
    PdfRasterizationError,
    _classify_pdfium_error_message,
    rasterize_pdf_work_item,
)


def _make_test_pdf(pdf_path: Path) -> None:
    page1 = Image.new("RGB", (300, 120), color=(255, 255, 255))
    page2 = Image.new("RGB", (200, 200), color=(240, 240, 240))
    page1.save(pdf_path, save_all=True, append_images=[page2])
    page1.close()
    page2.close()


def test_rasterize_pdf_work_item_preserves_page_order_and_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample doc.pdf"
    output_dir = tmp_path / "im-temp"
    _make_test_pdf(pdf_path)

    work_item = WorkItem(
        source_path=pdf_path,
        source_type="pdf",
        order_index=3,
        ordering_key=pdf_path.as_posix().lower(),
    )

    pages = rasterize_pdf_work_item(work_item=work_item, output_dir=output_dir)

    assert len(pages) == 2
    assert tuple(page.page_index for page in pages) == (0, 1)
    assert tuple(page.page_number for page in pages) == (1, 2)
    assert tuple(page.total_pages for page in pages) == (2, 2)
    assert tuple(page.source_order_index for page in pages) == (3, 3)
    assert all(page.source_pdf_path == pdf_path for page in pages)
    assert all(page.image_path.exists() for page in pages)
    assert pages[0].image_path.name.endswith("-p0001.png")
    assert pages[1].image_path.name.endswith("-p0002.png")


def test_rasterize_pdf_missing_source_maps_to_missing_input(tmp_path: Path) -> None:
    missing_pdf = tmp_path / "missing.pdf"
    work_item = WorkItem(
        source_path=missing_pdf,
        source_type="pdf",
        order_index=0,
        ordering_key=missing_pdf.as_posix().lower(),
    )

    try:
        rasterize_pdf_work_item(work_item=work_item, output_dir=tmp_path / "im-temp")
    except PdfRasterizationError as exc:
        assert exc.error_code == "missing_input"
        assert exc.source_path == missing_pdf
    else:
        raise AssertionError("Expected PdfRasterizationError for missing source")


def test_rasterize_pdf_corrupted_file_maps_to_corrupted_error(tmp_path: Path) -> None:
    invalid_pdf = tmp_path / "invalid.pdf"
    invalid_pdf.write_text("not a valid pdf", encoding="utf-8")
    work_item = WorkItem(
        source_path=invalid_pdf,
        source_type="pdf",
        order_index=0,
        ordering_key=invalid_pdf.as_posix().lower(),
    )

    try:
        rasterize_pdf_work_item(work_item=work_item, output_dir=tmp_path / "im-temp")
    except PdfRasterizationError as exc:
        assert exc.error_code in {"corrupted_pdf", "unreadable_pdf"}
    else:
        raise AssertionError("Expected PdfRasterizationError for corrupted PDF")


def test_classify_pdfium_error_message_supports_encrypted_case() -> None:
    assert _classify_pdfium_error_message("Incorrect password") == "encrypted_pdf"