from __future__ import annotations

import json

from common.gateway import GatewayError
from common.config import AppConfig, ConfigValidationError

from .discovery import build_work_items
from .page_processor import process_file
from .progress import GenerationProgressCallback, GenerationProgressContext, GenerationProgressEvent
from . import rasterizer


def _emit_stage(stage: str, *, status: str, detail: str = "") -> None:
    detail_token = f" detail={detail}" if detail else ""
    print(f"STAGE name={stage} status={status}{detail_token}")


def _emit_error(error_code: str, message: str) -> None:
    print(f"ERROR code={error_code} message={message}")


def _emit_progress(
    progress_callback: GenerationProgressCallback | None,
    event: GenerationProgressEvent,
) -> None:
    if progress_callback is not None:
        progress_callback(event)


def _count_total_jobs(config: AppConfig) -> int:
    total_jobs = 0
    for file_item in build_work_items(config):
        if file_item.source_type == "pdf":
            total_jobs += rasterizer.get_pdf_page_count(file_item.source_path)
        else:
            total_jobs += 1
    return total_jobs


def run_generation(
    config: AppConfig,
    progress_callback: GenerationProgressCallback | None = None,
) -> int:
    try:
        config.paths.output_dir.mkdir(parents=True, exist_ok=True)

        work_items = build_work_items(config)
        _emit_stage("discover_work_items", status="ok", detail=f"count={len(work_items)}")
        total_jobs = _count_total_jobs(config)
        progress_context = GenerationProgressContext(total_jobs=total_jobs)
        _emit_progress(
            progress_callback,
            GenerationProgressEvent(kind="stage_start", total_jobs=total_jobs),
        )

        metadata_records: list[dict] = []
        for file_item in work_items:
            print(f"> processing source {file_item.source_path.name}")
            metadata = process_file(
                config,
                file_item,
                progress_callback=progress_callback,
                progress_context=progress_context,
            )
            metadata_records.append(metadata)

        batch_path = config.paths.output_dir / "batch.json"
        batch_path.write_text(
            json.dumps({"documents": metadata_records}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _emit_stage("persist_batch", status="ok", detail=f"path={batch_path}")
        _emit_progress(
            progress_callback,
            GenerationProgressEvent(
                kind="batch_persisted",
                total_jobs=progress_context.total_jobs,
                completed_jobs=progress_context.completed_jobs,
                markdown_count=progress_context.markdown_count,
                markdown_path=batch_path,
            ),
        )
        _emit_progress(
            progress_callback,
            GenerationProgressEvent(
                kind="complete",
                total_jobs=progress_context.total_jobs,
                completed_jobs=progress_context.completed_jobs,
                markdown_count=progress_context.markdown_count,
            ),
        )

        return 0

    except ConfigValidationError as exc:
        _emit_error(exc.error_code, str(exc))
        _emit_progress(
            progress_callback,
            GenerationProgressEvent(kind="failed", error_code=exc.error_code, message=str(exc)),
        )
        return 2
    except GatewayError as exc:
        _emit_error(exc.error_code, str(exc))
        _emit_progress(
            progress_callback,
            GenerationProgressEvent(kind="failed", error_code=exc.error_code, message=str(exc)),
        )
        return 4
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        _emit_error("foundation_runtime_error", message)
        _emit_progress(
            progress_callback,
            GenerationProgressEvent(kind="failed", error_code="foundation_runtime_error", message=message),
        )
        return 1


def run_foundation_bootstrap(config: AppConfig) -> int:
    return run_generation(config)


