from __future__ import annotations

from pathlib import Path

from common.gateway import GatewayError, OcrResponse

from .config import AppConfig, ConfigValidationError
from .discovery import WorkItem, build_work_items
from .rasterizer import PdfPageRaster, rasterize_pdf_work_items
from .resizer import ImageResizeResult, resize_images_for_ocr
from .ocr_processor import SummaryAttempt, execute_ocr, execute_summaries
from .markdown_writer import PersistedMarkdownRecord, persist_ocr_markdown
from .metadata_writer import PersistedMetadataRecord, persist_document_metadata


def _emit_stage(stage: str, *, status: str, detail: str = "") -> None:
    detail_token = f" detail={detail}" if detail else ""
    print(f"STAGE name={stage} status={status}{detail_token}")


def _emit_error(error_code: str, message: str) -> None:
    print(f"ERROR code={error_code} message={message}")    


def _collect_images_for_resizing(
    work_items: tuple[WorkItem, ...],
    pdf_pages: tuple[PdfPageRaster, ...],
) -> tuple[Path, ...]:
    # start adding the pages from lose images
    image_paths = [work_item.source_path.resolve() for work_item in work_items if work_item.source_type == "image"]
    # and then the rasterized pages from PDFs
    image_paths.extend(page.image_path.resolve() for page in pdf_pages)
    # Question: If work items where sorted, do we need to sort again here?
    return tuple(sorted(set(image_paths), key=lambda path: path.name.lower()))


def persist_markdown(
    config: AppConfig,
    ocr_responses: tuple[OcrResponse, ...],
    pdf_pages: tuple[PdfPageRaster, ...],
    resized_images: tuple[ImageResizeResult, ...],
) -> tuple[PersistedMarkdownRecord, ...]:
    return persist_ocr_markdown(
        ocr_responses=ocr_responses,
        pdf_pages=pdf_pages,
        resized_images=resized_images,
        md_temp_dir=config.paths.md_temp_dir,
        model_name=config.ocr_model.model_name,
        overwrite=config.runtime.overwrite,
    )


def persist_metadata(
    config: AppConfig,
    persisted_markdown: tuple[PersistedMarkdownRecord, ...],
    ocr_responses: tuple[OcrResponse, ...],
    summary_attempts: tuple[SummaryAttempt, ...],
) -> tuple[PersistedMetadataRecord, ...]:
    summary_by_image_path = {
        attempt.image_path.resolve(): attempt.summary_text
        for attempt in summary_attempts
    }
    return persist_document_metadata(
        markdown_records=persisted_markdown,
        ocr_responses=ocr_responses,
        summary_by_image_path=summary_by_image_path,
        metadata_temp_dir=config.paths.metadata_temp_dir,
        overwrite=config.runtime.overwrite,
    )


def run_foundation_bootstrap(config: AppConfig) -> int:
    try:
        config.paths.output_dir.mkdir(parents=True, exist_ok=True)
        config.paths.temp_dir.mkdir(parents=True, exist_ok=True)

        work_items = build_work_items(config)
        _emit_stage("discover_work_items", status="ok", detail=f"count={len(work_items)}")

        pdf_pages = rasterize_pdf_work_items(work_items, config.paths.im_temp_dir)
        _emit_stage("rasterize_pdf", status="ok", detail=f"pages={len(pdf_pages)}")

        image_paths = _collect_images_for_resizing(work_items, pdf_pages)

        resized_images = resize_images_for_ocr(image_paths, config.paths.output_dir, config.image.max_longest_edge_px)
        _emit_stage("resize_images", status="ok", detail=f"images={len(resized_images)}")

        if config.runtime.dry_run:
            _emit_stage("execute_ocr", status="skipped", detail="reason=dry_run_enabled")
            _emit_stage("execute_summary", status="skipped", detail="reason=dry_run_enabled")
            _emit_stage("persist_markdown", status="skipped", detail="reason=dry_run_enabled")
            _emit_stage("persist_metadata", status="skipped", detail="reason=dry_run_enabled")
            return 0

        ocr_responses = execute_ocr(config, resized_images)
        _emit_stage("execute_ocr", status="ok", detail=f"responses={len(ocr_responses)}")

        summary_attempts = execute_summaries(config, ocr_responses)
        summary_failures = sum(1 for attempt in summary_attempts if attempt.failed)
        _emit_stage("execute_summary", status="ok", detail=f"responses={len(summary_attempts)} failures={summary_failures}")

        persisted_records = persist_markdown(config, ocr_responses, pdf_pages, resized_images)
        _emit_stage("persist_markdown", status="ok", detail=f"records={len(persisted_records)}")

        metadata_records = persist_metadata(config, persisted_records, ocr_responses, summary_attempts)
        _emit_stage("persist_metadata", status="ok", detail=f"records={len(metadata_records)}")
        return 0
    
    except ConfigValidationError as exc:
        _emit_error(exc.error_code, str(exc))
        return 2
    except GatewayError as exc:
        _emit_error(exc.error_code, str(exc))
        return 4
    except Exception as exc:
        _emit_error("foundation_runtime_error", f"{type(exc).__name__}: {exc}")
        return 1


def run_phase_one_bootstrap(config: AppConfig) -> int:
    return run_foundation_bootstrap(config)
