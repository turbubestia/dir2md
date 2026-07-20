from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common.config import AppConfig
from .discovery import FileItem
from . import ocr_processor, rasterizer, summarize
from .progress import GenerationProgressCallback, GenerationProgressContext, GenerationProgressEvent


def _build_output_markdown_path(config: AppConfig, file_item: FileItem) -> Path:
    return config.paths.output_dir / f"{file_item.source_path.stem}.md"


def _emit_progress(
    progress_callback: GenerationProgressCallback | None,
    event: GenerationProgressEvent,
) -> None:
    if progress_callback is not None:
        progress_callback(event)


def process_file(
    config: AppConfig,
    file_item: FileItem,
    *,
    progress_callback: GenerationProgressCallback | None = None,
    progress_context: GenerationProgressContext | None = None,
) -> dict[str, Any]:
    output_path = _build_output_markdown_path(config, file_item)
    markdown_buffer: list[str] = []
    page_summaries: list[str] = []
    page_count = 1
    status = "ok"

    try:
        if file_item.source_type == "pdf":
            page_count = rasterizer.get_pdf_page_count(file_item.source_path)
            pages = range(1, page_count + 1)
        else:
            pages = (1,)

        for page_number in pages:
            total_jobs = progress_context.total_jobs if progress_context is not None else page_count
            completed_jobs = progress_context.completed_jobs if progress_context is not None else 0
            markdown_count = progress_context.markdown_count if progress_context is not None else 0
            _emit_progress(
                progress_callback,
                GenerationProgressEvent(
                    kind="ocr_item_start",
                    total_jobs=total_jobs,
                    completed_jobs=completed_jobs,
                    markdown_count=markdown_count,
                    source_path=file_item.source_path,
                    source_file_name=file_item.source_path.name,
                    source_type=file_item.source_type,
                    page_number=page_number,
                    markdown_path=output_path,
                ),
            )
            image = rasterizer.rasterize_page(
                file_item.source_path,
                max_edge_size=config.md_gen.image.max_longest_edge_px,
                page_number=page_number if file_item.source_type == "pdf" else None,
            )
            try:
                page_markdown = ocr_processor.extract_markdown(config, image)
                page_summary = summarize.summarize_page(config, page_markdown)
                markdown_buffer.append(page_markdown)
                page_summaries.append(page_summary)
                if progress_context is not None:
                    progress_context.completed_jobs += 1
                    progress_context.markdown_count += 1
                    completed_jobs = progress_context.completed_jobs
                    markdown_count = progress_context.markdown_count
                else:
                    completed_jobs += 1
                    markdown_count += 1
                _emit_progress(
                    progress_callback,
                    GenerationProgressEvent(
                        kind="ocr_item_complete",
                        total_jobs=total_jobs,
                        completed_jobs=completed_jobs,
                        markdown_count=markdown_count,
                        source_path=file_item.source_path,
                        source_file_name=file_item.source_path.name,
                        source_type=file_item.source_type,
                        page_number=page_number,
                        markdown_path=output_path,
                    ),
                )
                print(f"page {page_number} done")
            finally:
                image.close()

        document_summary = summarize.summarize_document(config, page_summaries)
    except Exception as exc:
        print(f"ERROR processing {file_item.source_path.name}: {exc}")
        document_summary = ""
        status = "failed"

    if output_path.exists() and not config.runtime.overwrite:
        print(f"> skipping file {output_path}: already exists")
    else:
        output_path.write_text("\n\n".join(markdown_buffer).strip() + "\n", encoding="utf-8")

    return {
        "source_file_name": file_item.source_path.name,
        "file_type": file_item.source_type,
        "page_count": page_count,
        "date_of_process": datetime.now(timezone.utc).isoformat(),
        "summary": document_summary,
        "markdown_file": output_path.name,
        "status": status,
    }
