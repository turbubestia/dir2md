from __future__ import annotations

from pathlib import Path
from typing import Literal

import pypdfium2 as pdfium
from PIL import Image, ImageOps

RasterizationErrorCode = Literal[
    "unsupported_file",
    "missing_input",
    "encrypted_pdf",
    "corrupted_pdf",
    "unreadable_pdf",
]

_SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


class RasterizationError(RuntimeError):
    def __init__(self, source_path: Path, error_code: RasterizationErrorCode, message: str):
        super().__init__(message)
        self.source_path = source_path
        self.error_code = error_code


def _classify_pdfium_error(message: str) -> RasterizationErrorCode:
    normalized = message.lower()
    if "password" in normalized or "encrypted" in normalized:
        return "encrypted_pdf"
    if "data format" in normalized or "syntax" in normalized:
        return "corrupted_pdf"
    return "unreadable_pdf"


def _target_dimensions(width: int, height: int, max_longest_edge_px: int) -> tuple[int, int]:
    if max(width, height) <= max_longest_edge_px:
        return width, height
    if width >= height:
        return max_longest_edge_px, max(1, int(height * max_longest_edge_px / width))
    return max(1, int(width * max_longest_edge_px / height)), max_longest_edge_px


def resize_image(image: Image.Image, max_longest_edge_px: int) -> Image.Image:
    """Return a resized copy; keep original dimensions if already within bounds."""
    original_width, original_height = image.size
    target_width, target_height = _target_dimensions(original_width, original_height, max_longest_edge_px)
    if (target_width, target_height) == (original_width, original_height):
        return image.copy()
    return image.resize((target_width, target_height), Image.Resampling.LANCZOS)


def rasterize_page(source_path: Path, max_edge_size: int, page_number: int | None = None) -> Image.Image:
    """Return a single resized PIL.Image.Image for the requested page (1-based) or the whole image."""
    suffix = source_path.suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise RasterizationError(source_path, "unsupported_file", f"Unsupported file type: {source_path}")
    if not source_path.exists():
        raise RasterizationError(source_path, "missing_input", f"Source does not exist: {source_path}")

    if suffix == ".pdf":
        try:
            # Pdfium reads the PDF container/catalog first, then defers heavy page decoding.
            # This keeps open-time cost low even for large multi-page documents.
            document = pdfium.PdfDocument(source_path)
        except pdfium.PdfiumError as exc:
            error_code = _classify_pdfium_error(str(exc))
            raise RasterizationError(
                source_path,
                error_code,
                f"Failed to open PDF {source_path}: {exc}",
            ) from exc

        try:
            total_pages = len(document)
            if page_number is None:
                page_number = 1
            if page_number < 1 or page_number > total_pages:
                raise RasterizationError(
                    source_path,
                    "unreadable_pdf",
                    f"Invalid page number {page_number} for PDF with {total_pages} page(s)",
                )

            # Accessing one page triggers work for that page only.
            # Pdfium does not rasterize or fully load the rest of the document here.
            page = document.get_page(page_number - 1)
            try:
                bitmap = page.render(scale=1)
                image = bitmap.to_pil()
            except pdfium.PdfiumError as exc:
                error_code = _classify_pdfium_error(str(exc))
                raise RasterizationError(
                    source_path,
                    error_code,
                    f"Failed to rasterize page {page_number} for {source_path}: {exc}",
                ) from exc
            finally:
                page.close()
        finally:
            document.close()
    else:
        image = Image.open(source_path)
        image = ImageOps.exif_transpose(image)

    try:
        resized = resize_image(image, max_edge_size)
    finally:
        image.close()

    return resized


def get_pdf_page_count(source_path: Path) -> int:
    """Return the number of pages in a PDF; close the document before returning."""
    if not source_path.exists():
        raise RasterizationError(source_path, "missing_input", f"Source does not exist: {source_path}")
    if source_path.suffix.lower() != ".pdf":
        raise RasterizationError(source_path, "unsupported_file", f"Not a PDF: {source_path}")

    try:
        # Page count comes from document structure metadata.
        # Pdfium can return this without rendering every page into bitmaps.
        document = pdfium.PdfDocument(source_path)
    except pdfium.PdfiumError as exc:
        error_code = _classify_pdfium_error(str(exc))
        raise RasterizationError(
            source_path,
            error_code,
            f"Failed to open PDF {source_path}: {exc}",
        ) from exc

    try:
        return len(document)
    finally:
        document.close()