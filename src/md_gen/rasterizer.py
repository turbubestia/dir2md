from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Literal

import pypdfium2 as pdfium

from .discovery import WorkItem

PdfRasterizationErrorCode = Literal[
    "missing_input",
    "encrypted_pdf",
    "corrupted_pdf",
    "unreadable_pdf",
]


@dataclass(frozen=True)
class PdfPageRaster:
    source_pdf_path: Path
    source_order_index: int
    source_ordering_key: str
    page_index: int
    page_number: int
    total_pages: int
    image_path: Path
    image_width: int
    image_height: int


class PdfRasterizationError(RuntimeError):
    def __init__(self, source_path: Path, error_code: PdfRasterizationErrorCode, message: str):
        super().__init__(message)
        self.source_path = source_path
        self.error_code = error_code


def _classify_pdfium_error_message(message: str) -> PdfRasterizationErrorCode:
    normalized = message.lower()
    if "password" in normalized or "encrypted" in normalized:
        return "encrypted_pdf"
    if "data format" in normalized or "syntax" in normalized:
        return "corrupted_pdf"
    return "unreadable_pdf"


def _sanitize_stem(path: Path) -> str:
    cleaned = []
    for char in path.stem.lower():
        if char.isalnum() or char in {"-", "_"}:
            cleaned.append(char)
        else:
            cleaned.append("-")
    return "".join(cleaned).strip("-") or "document"


def _build_output_image_path(source_pdf_path: Path, page_number: int, output_dir: Path) -> Path:
    source_hash = sha1(source_pdf_path.as_posix().encode("utf-8")).hexdigest()[:10]
    output_name = f"{_sanitize_stem(source_pdf_path)}-{source_hash}-p{page_number:04d}.png"
    return output_dir / output_name


def rasterize_pdf_work_item(
    work_item: WorkItem,
    output_dir: Path,
    render_scale: float = 2.0,
) -> tuple[PdfPageRaster, ...]:
    source_pdf_path = work_item.source_path
    if not source_pdf_path.exists():
        raise PdfRasterizationError(
            source_path=source_pdf_path,
            error_code="missing_input",
            message=f"Source PDF does not exist: {source_pdf_path}",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        document = pdfium.PdfDocument(source_pdf_path)
    except pdfium.PdfiumError as exc:
        error_code = _classify_pdfium_error_message(str(exc))
        raise PdfRasterizationError(
            source_path=source_pdf_path,
            error_code=error_code,
            message=f"Failed to open PDF {source_pdf_path}: {exc}",
        ) from exc

    pages: list[PdfPageRaster] = []
    try:
        total_pages = len(document)
        for page_index in range(total_pages):
            page = document.get_page(page_index)
            page_number = page_index + 1
            try:
                bitmap = page.render(scale=render_scale)
                image = bitmap.to_pil()
                output_path = _build_output_image_path(source_pdf_path, page_number, output_dir)
                image_width, image_height = image.size
                image.save(output_path, format="PNG")
                image.close()
            except pdfium.PdfiumError as exc:
                error_code = _classify_pdfium_error_message(str(exc))
                raise PdfRasterizationError(
                    source_path=source_pdf_path,
                    error_code=error_code,
                    message=f"Failed to rasterize page {page_number} for {source_pdf_path}: {exc}",
                ) from exc
            finally:
                page.close()

            pages.append(
                PdfPageRaster(
                    source_pdf_path=source_pdf_path,
                    source_order_index=work_item.order_index,
                    source_ordering_key=work_item.ordering_key,
                    page_index=page_index,
                    page_number=page_number,
                    total_pages=total_pages,
                    image_path=output_path,
                    image_width=image_width,
                    image_height=image_height,
                )
            )
    finally:
        document.close()

    return tuple(pages)


def rasterize_pdf_work_items(
    work_items: tuple[WorkItem, ...],
    output_dir: Path,
    render_scale: float = 2.0,
) -> tuple[PdfPageRaster, ...]:
    all_pages: list[PdfPageRaster] = []
    for work_item in work_items:
        if work_item.source_type != "pdf":
            continue
        all_pages.extend(rasterize_pdf_work_item(work_item, output_dir=output_dir, render_scale=render_scale))
    return tuple(all_pages)