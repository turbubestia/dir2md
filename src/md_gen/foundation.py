from __future__ import annotations

from .config import AppConfig
from .discovery import WorkItem, build_work_items
from .rasterizer import PdfPageRaster, rasterize_pdf_work_items


def ensure_phase_one_directories(config: AppConfig) -> None:
    config.paths.im_temp_dir.mkdir(parents=True, exist_ok=True)
    config.paths.md_temp_dir.mkdir(parents=True, exist_ok=True)
    config.paths.log_file.parent.mkdir(parents=True, exist_ok=True)


def prepare_work_items(config: AppConfig) -> tuple[WorkItem, ...]:
    return build_work_items(config)


def rasterize_pdf_items(config: AppConfig, work_items: tuple[WorkItem, ...]) -> tuple[PdfPageRaster, ...]:
    return rasterize_pdf_work_items(work_items=work_items, output_dir=config.paths.im_temp_dir)


def run_foundation_bootstrap(config: AppConfig) -> int:
    ensure_phase_one_directories(config)
    work_items = prepare_work_items(config)
    rasterize_pdf_items(config, work_items)
    return 0


def run_phase_one_bootstrap(config: AppConfig) -> int:
    return run_foundation_bootstrap(config)
