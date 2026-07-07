from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path

from .gateway import OcrResponse
from .rasterizer import PdfPageRaster
from .resizer import ImageResizeResult
from .token_budget import ImageTokenBudgetReport


@dataclass(frozen=True)
class PersistedMarkdownRecord:
    source_image_path: Path
    source_file_path: Path
    source_type: str
    source_page_index: int | None
    output_markdown_path: Path
    estimated_vision_tokens: int


def _sanitize_stem(path: Path) -> str:
    cleaned = []
    for char in path.stem.lower():
        if char.isalnum() or char in {"-", "_"}:
            cleaned.append(char)
        else:
            cleaned.append("-")
    return "".join(cleaned).strip("-") or "document"


def _build_output_markdown_path(
    md_temp_dir: Path,
    source_file_path: Path,
    source_type: str,
    source_page_index: int | None,
) -> Path:
    page_suffix = f"-p{source_page_index + 1:04d}" if source_page_index is not None else ""
    key = f"{source_file_path.as_posix()}|{source_type}|{source_page_index}"
    path_hash = sha1(key.encode("utf-8")).hexdigest()[:10]
    filename = f"{_sanitize_stem(source_file_path)}{page_suffix}-{path_hash}.md"
    return md_temp_dir / filename


def _format_metadata_header(
    source_file_path: Path,
    source_type: str,
    source_page_index: int | None,
    generated_at_utc: str,
    model_name: str,
    image_width: int,
    image_height: int,
    estimated_vision_tokens: int,
) -> str:
    lines = [
        "---",
        f"source_file_name: {source_file_path.name}",
        f"source_file_path: {source_file_path.as_posix()}",
        f"source_type: {source_type}",
    ]
    if source_page_index is not None:
        lines.append(f"source_page_index: {source_page_index}")
    lines.extend(
        [
            f"generated_at_utc: {generated_at_utc}",
            f"model_name: {model_name}",
            f"image_dimensions: {image_width}x{image_height}",
            f"estimated_vision_tokens: {estimated_vision_tokens}",
            "---",
            "",
        ]
    )
    return "\n".join(lines)


def persist_ocr_markdown(
    ocr_responses: tuple[OcrResponse, ...],
    pdf_pages: tuple[PdfPageRaster, ...],
    resized_images: tuple[ImageResizeResult, ...],
    token_reports: tuple[ImageTokenBudgetReport, ...],
    md_temp_dir: Path,
    model_name: str,
    overwrite: bool,
) -> tuple[PersistedMarkdownRecord, ...]:
    md_temp_dir.mkdir(parents=True, exist_ok=True)
    generated_at_utc = datetime.now(timezone.utc).isoformat()

    pdf_page_by_image = {page.image_path.resolve(): page for page in pdf_pages}
    resized_by_image = {image.output_image_path.resolve(): image for image in resized_images}
    token_by_image = {Path(report.image_path).resolve(): report for report in token_reports}

    persisted: list[PersistedMarkdownRecord] = []
    for response in ocr_responses:
        image_path = response.image_path.resolve()
        resized = resized_by_image.get(image_path)
        token_report = token_by_image.get(image_path)
        if resized is None or token_report is None:
            raise ValueError(f"Missing resize/token data for OCR response image: {image_path}")

        pdf_page = pdf_page_by_image.get(image_path)
        if pdf_page is not None:
            source_file_path = pdf_page.source_pdf_path.resolve()
            source_type = "pdf_page"
            source_page_index = pdf_page.page_index
        else:
            source_file_path = resized.source_image_path.resolve()
            source_type = "image"
            source_page_index = None

        output_path = _build_output_markdown_path(
            md_temp_dir=md_temp_dir,
            source_file_path=source_file_path,
            source_type=source_type,
            source_page_index=source_page_index,
        )
        if output_path.exists() and not overwrite:
            raise FileExistsError(
                f"Markdown output already exists: {output_path}. "
                "Re-run with --overwrite to replace existing markdown outputs."
            )

        header = _format_metadata_header(
            source_file_path=source_file_path,
            source_type=source_type,
            source_page_index=source_page_index,
            generated_at_utc=generated_at_utc,
            model_name=model_name,
            image_width=resized.resized_width,
            image_height=resized.resized_height,
            estimated_vision_tokens=token_report.estimated_tokens,
        )
        output_path.write_text(header + response.markdown_text.strip() + "\n", encoding="utf-8")

        persisted.append(
            PersistedMarkdownRecord(
                source_image_path=image_path,
                source_file_path=source_file_path,
                source_type=source_type,
                source_page_index=source_page_index,
                output_markdown_path=output_path,
                estimated_vision_tokens=token_report.estimated_tokens,
            )
        )

    return tuple(persisted)