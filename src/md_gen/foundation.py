from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable, TypeVar

from .config import AppConfig
from .discovery import WorkItem, build_work_items
from .gateway import LlamaOcrGateway, OcrResponse, build_default_ocr_requests
from .markdown_writer import PersistedMarkdownRecord, persist_ocr_markdown
from .rasterizer import PdfPageRaster, rasterize_pdf_work_items
from .resizer import ImageResizeResult, resize_images_for_ocr
from .token_budget import ImageTokenBudgetReport, enforce_token_budget, evaluate_token_budget_for_images

T = TypeVar("T")


class PlainTextRunLogger:
    def __init__(self, log_file: Path):
        self._log_file = log_file

    def _append_line(self, message: str) -> None:
        with self._log_file.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")

    def log_run_start(self, *, dry_run: bool, overwrite: bool, model_name: str, source_count: int) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        self._append_line(
            "RUN_START "
            f"timestamp={timestamp} dry_run={dry_run} overwrite={overwrite} "
            f"model={model_name} source_count={source_count}"
        )

    def log_stage(self, *, stage: str, status: str, duration_seconds: float, detail: str = "") -> None:
        detail_suffix = f" detail={detail}" if detail else ""
        self._append_line(
            f"STAGE name={stage} status={status} duration_seconds={duration_seconds:.3f}{detail_suffix}"
        )

    def log_run_summary(
        self,
        *,
        status: str,
        duration_seconds: float,
        discovered_work_items: int,
        rasterized_pages: int,
        resized_images: int,
        token_warnings: int,
        token_errors: int,
        persisted_markdown: int,
        error: str | None = None,
    ) -> None:
        error_suffix = f" error={error}" if error else ""
        self._append_line(
            "RUN_SUMMARY "
            f"status={status} duration_seconds={duration_seconds:.3f} "
            f"discovered_work_items={discovered_work_items} rasterized_pages={rasterized_pages} "
            f"resized_images={resized_images} token_warnings={token_warnings} token_errors={token_errors} "
            f"persisted_markdown={persisted_markdown}{error_suffix}"
        )


def _time_stage(action: Callable[[], T]) -> tuple[T, float]:
    started = perf_counter()
    result = action()
    duration = perf_counter() - started
    return result, duration


def ensure_phase_one_directories(config: AppConfig) -> None:
    config.paths.im_temp_dir.mkdir(parents=True, exist_ok=True)
    config.paths.md_temp_dir.mkdir(parents=True, exist_ok=True)
    config.paths.log_file.parent.mkdir(parents=True, exist_ok=True)


def prepare_work_items(config: AppConfig) -> tuple[WorkItem, ...]:
    return build_work_items(config)


def rasterize_pdf_items(config: AppConfig, work_items: tuple[WorkItem, ...]) -> tuple[PdfPageRaster, ...]:
    return rasterize_pdf_work_items(work_items=work_items, output_dir=config.paths.im_temp_dir)


def _collect_images_for_resizing(
    work_items: tuple[WorkItem, ...],
    pdf_pages: tuple[PdfPageRaster, ...],
) -> tuple[Path, ...]:
    image_paths = [work_item.source_path.resolve() for work_item in work_items if work_item.source_type == "image"]
    image_paths.extend(page.image_path.resolve() for page in pdf_pages)
    return tuple(sorted(set(image_paths), key=lambda path: path.as_posix().lower()))


def resize_images(
    config: AppConfig,
    work_items: tuple[WorkItem, ...],
    pdf_pages: tuple[PdfPageRaster, ...],
) -> tuple[ImageResizeResult, ...]:
    image_paths = _collect_images_for_resizing(work_items, pdf_pages)
    return resize_images_for_ocr(
        source_image_paths=image_paths,
        output_dir=config.paths.im_temp_dir,
        max_longest_edge_px=config.image.max_longest_edge_px,
    )


def validate_token_budget(
    config: AppConfig,
    resized_images: tuple[ImageResizeResult, ...],
) -> tuple[ImageTokenBudgetReport, ...]:
    reports = evaluate_token_budget_for_images(
        resized_images=resized_images,
        token_threshold=config.image.token_threshold,
    )
    enforce_token_budget(reports)
    return reports


def execute_ocr(
    config: AppConfig,
    resized_images: tuple[ImageResizeResult, ...],
) -> tuple[OcrResponse, ...]:
    image_paths = tuple(image.output_image_path for image in resized_images)
    ocr_requests = build_default_ocr_requests(image_paths)
    with LlamaOcrGateway(
        endpoint_url=config.model.endpoint_url,
        model_name=config.model.model_name,
        request_timeout_seconds=config.model.request_timeout_seconds,
        request_max_retries=config.model.request_max_retries,
    ) as gateway:
        return gateway.send_ocr_requests(ocr_requests)


def persist_markdown(
    config: AppConfig,
    ocr_responses: tuple[OcrResponse, ...],
    pdf_pages: tuple[PdfPageRaster, ...],
    resized_images: tuple[ImageResizeResult, ...],
    token_reports: tuple[ImageTokenBudgetReport, ...],
) -> tuple[PersistedMarkdownRecord, ...]:
    return persist_ocr_markdown(
        ocr_responses=ocr_responses,
        pdf_pages=pdf_pages,
        resized_images=resized_images,
        token_reports=token_reports,
        md_temp_dir=config.paths.md_temp_dir,
        model_name=config.model.model_name,
        overwrite=config.runtime.overwrite,
    )


def run_foundation_bootstrap(config: AppConfig) -> int:
    started_at = perf_counter()

    ensure_phase_one_directories(config)
    logger = PlainTextRunLogger(config.paths.log_file)
    logger.log_run_start(
        dry_run=config.runtime.dry_run,
        overwrite=config.runtime.overwrite,
        model_name=config.model.model_name,
        source_count=len(config.paths.source_paths),
    )

    work_items: tuple[WorkItem, ...] = tuple()
    pdf_pages: tuple[PdfPageRaster, ...] = tuple()
    resized_images: tuple[ImageResizeResult, ...] = tuple()
    token_reports: tuple[ImageTokenBudgetReport, ...] = tuple()
    persisted_records: tuple[PersistedMarkdownRecord, ...] = tuple()

    try:
        work_items, duration = _time_stage(lambda: prepare_work_items(config))
        logger.log_stage(
            stage="discover_work_items",
            status="ok",
            duration_seconds=duration,
            detail=f"count={len(work_items)}",
        )

        pdf_pages, duration = _time_stage(lambda: rasterize_pdf_items(config, work_items))
        logger.log_stage(
            stage="rasterize_pdf",
            status="ok",
            duration_seconds=duration,
            detail=f"pages={len(pdf_pages)}",
        )

        resized_images, duration = _time_stage(lambda: resize_images(config, work_items, pdf_pages))
        logger.log_stage(
            stage="resize_images",
            status="ok",
            duration_seconds=duration,
            detail=f"images={len(resized_images)}",
        )

        token_reports, duration = _time_stage(lambda: validate_token_budget(config, resized_images))
        warnings = sum(1 for report in token_reports if report.status == "warning")
        errors = sum(1 for report in token_reports if report.status == "error")
        logger.log_stage(
            stage="validate_token_budget",
            status="ok",
            duration_seconds=duration,
            detail=f"warnings={warnings} errors={errors}",
        )

        if config.runtime.dry_run:
            logger.log_stage(
                stage="execute_ocr",
                status="skipped",
                duration_seconds=0.0,
                detail="reason=dry_run_enabled",
            )
            logger.log_stage(
                stage="persist_markdown",
                status="skipped",
                duration_seconds=0.0,
                detail="reason=dry_run_enabled",
            )
        else:
            ocr_responses, duration = _time_stage(lambda: execute_ocr(config, resized_images))
            logger.log_stage(
                stage="execute_ocr",
                status="ok",
                duration_seconds=duration,
                detail=f"responses={len(ocr_responses)}",
            )

            persisted_records, duration = _time_stage(
                lambda: persist_markdown(config, ocr_responses, pdf_pages, resized_images, token_reports)
            )
            logger.log_stage(
                stage="persist_markdown",
                status="ok",
                duration_seconds=duration,
                detail=f"records={len(persisted_records)}",
            )

        total_duration = perf_counter() - started_at
        logger.log_run_summary(
            status="ok",
            duration_seconds=total_duration,
            discovered_work_items=len(work_items),
            rasterized_pages=len(pdf_pages),
            resized_images=len(resized_images),
            token_warnings=sum(1 for report in token_reports if report.status == "warning"),
            token_errors=sum(1 for report in token_reports if report.status == "error"),
            persisted_markdown=len(persisted_records),
        )
        return 0
    except Exception as exc:
        total_duration = perf_counter() - started_at
        logger.log_run_summary(
            status="failed",
            duration_seconds=total_duration,
            discovered_work_items=len(work_items),
            rasterized_pages=len(pdf_pages),
            resized_images=len(resized_images),
            token_warnings=sum(1 for report in token_reports if report.status == "warning"),
            token_errors=sum(1 for report in token_reports if report.status == "error"),
            persisted_markdown=len(persisted_records),
            error=type(exc).__name__,
        )
        raise


def run_phase_one_bootstrap(config: AppConfig) -> int:
    return run_foundation_bootstrap(config)
