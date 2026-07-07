from __future__ import annotations

from pathlib import Path

from .config import AppConfig
from .discovery import WorkItem, build_work_items
from .gateway import LlamaOcrGateway, OcrResponse, build_default_ocr_requests
from .rasterizer import PdfPageRaster, rasterize_pdf_work_items
from .resizer import ImageResizeResult, resize_images_for_ocr
from .token_budget import ImageTokenBudgetReport, enforce_token_budget, evaluate_token_budget_for_images


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


def run_foundation_bootstrap(config: AppConfig) -> int:
    ensure_phase_one_directories(config)
    work_items = prepare_work_items(config)
    pdf_pages = rasterize_pdf_items(config, work_items)
    resized_images = resize_images(config, work_items, pdf_pages)
    validate_token_budget(config, resized_images)
    if not config.runtime.dry_run:
        execute_ocr(config, resized_images)
    return 0


def run_phase_one_bootstrap(config: AppConfig) -> int:
    return run_foundation_bootstrap(config)
