from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

from .config import AppConfig, ConfigValidationError
from .discovery import WorkItem, build_work_items

from common.llama_gateway import (
    GatewayError,
    OcrResponse,
    LlamaOcrGateway,
    SummaryRequest,
    LlamaSummaryGateway,
    build_default_ocr_requests,
)

from .markdown_writer import PersistedMarkdownRecord, persist_ocr_markdown
from .metadata_writer import PersistedMetadataRecord, persist_document_metadata
from .rasterizer import PdfPageRaster, rasterize_pdf_work_items
from .resizer import ImageResizeResult, resize_images_for_ocr
from .token_budget import (
    ImageTokenBudgetReport,
    TokenBudgetValidationError,
    enforce_token_budget,
    evaluate_token_budget_for_images,
)

T = TypeVar("T")


@dataclass(frozen=True)
class SummaryAttempt:
    image_path: Path
    summary_text: str
    failed: bool
    error_code: str | None


def _emit_stage(stage: str, *, status: str, detail: str = "") -> None:
    detail_token = f" detail={detail}" if detail else ""
    print(f"STAGE name={stage} status={status}{detail_token}")


def _emit_error(error_code: str, message: str) -> None:
    print(f"ERROR code={error_code} message={message}")


def _time_stage(action: Callable[[], T]) -> T:
    return action()


def _load_prompt_file(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    return text


def load_summary_system_prompt(config: AppConfig) -> str:
    override_path = config.prompts.summary_prompt_override_path
    default_path = config.prompts.summary_prompt_default_path

    if override_path is not None:
        override_text = _load_prompt_file(override_path)
        if override_text is not None:
            print(f"PROMPT status=loaded source=override path={override_path}")
            return override_text
        print(f"PROMPT status=fallback source=override_unreadable path={override_path}")

    default_text = _load_prompt_file(default_path)
    if default_text is not None:
        print(f"PROMPT status=loaded source=default path={default_path}")
        return default_text

    print("PROMPT status=fallback source=builtin")
    return config.prompts.summary_prompt_builtin_text


def ensure_phase_one_directories(config: AppConfig) -> None:
    config.paths.output_dir.mkdir(parents=True, exist_ok=True)
    config.paths.temp_dir.mkdir(parents=True, exist_ok=True)
    config.paths.im_temp_dir.mkdir(parents=True, exist_ok=True)
    config.paths.md_temp_dir.mkdir(parents=True, exist_ok=True)
    config.paths.metadata_temp_dir.mkdir(parents=True, exist_ok=True)


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
    unique_image_paths: list[Path] = []
    seen: set[Path] = set()
    for image in resized_images:
        resolved_path = image.output_image_path.resolve()
        if resolved_path in seen:
            continue
        seen.add(resolved_path)
        unique_image_paths.append(resolved_path)

    ocr_requests = build_default_ocr_requests(tuple(unique_image_paths))
    with LlamaOcrGateway(
        endpoint_url=config.ocr_model.endpoint_url,
        model_name=config.ocr_model.model_name,
        request_timeout_seconds=config.ocr_model.request_timeout_seconds,
        request_max_retries=config.ocr_model.request_max_retries,
    ) as gateway:
        responses: list[OcrResponse] = []
        for request in ocr_requests:
            print(f"> processing image {request.image_path}")
            responses.append(gateway.send_ocr_request(request))
        return tuple(responses)


def execute_summaries(
    config: AppConfig,
    ocr_responses: tuple[OcrResponse, ...],
) -> tuple[SummaryAttempt, ...]:
    attempts: list[SummaryAttempt] = []
    system_prompt = load_summary_system_prompt(config)
    with LlamaSummaryGateway(
        endpoint_url=config.language_model.endpoint_url,
        model_name=config.language_model.model_name,
        request_timeout_seconds=config.language_model.request_timeout_seconds,
        request_max_retries=config.language_model.request_max_retries,
    ) as gateway:
        for response in ocr_responses:
            try:
                print(f"> processing summary for image {response.image_path}")
                summary_response = gateway.send_summary_request(
                    SummaryRequest(source_text=response.markdown_text, system_prompt=system_prompt)
                )
            except GatewayError as exc:
                attempts.append(
                    SummaryAttempt(
                        image_path=response.image_path.resolve(),
                        summary_text="",
                        failed=True,
                        error_code=exc.error_code,
                    )
                )
            except Exception:
                attempts.append(
                    SummaryAttempt(
                        image_path=response.image_path.resolve(),
                        summary_text="",
                        failed=True,
                        error_code="unknown_error",
                    )
                )
            else:
                attempts.append(
                    SummaryAttempt(
                        image_path=response.image_path.resolve(),
                        summary_text=summary_response.summary_text,
                        failed=False,
                        error_code=None,
                    )
                )
    return tuple(attempts)


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
        ensure_phase_one_directories(config)

        work_items = _time_stage(lambda: prepare_work_items(config))
        _emit_stage("discover_work_items", status="ok", detail=f"count={len(work_items)}")

        pdf_pages = _time_stage(lambda: rasterize_pdf_items(config, work_items))
        _emit_stage("rasterize_pdf", status="ok", detail=f"pages={len(pdf_pages)}")

        resized_images = _time_stage(lambda: resize_images(config, work_items, pdf_pages))
        _emit_stage("resize_images", status="ok", detail=f"images={len(resized_images)}")

        token_reports = _time_stage(lambda: validate_token_budget(config, resized_images))
        warnings = sum(1 for report in token_reports if report.status == "warning")
        errors = sum(1 for report in token_reports if report.status == "error")
        _emit_stage("validate_token_budget", status="ok", detail=f"warnings={warnings} errors={errors}")

        if config.runtime.dry_run:
            _emit_stage("execute_ocr", status="skipped", detail="reason=dry_run_enabled")
            _emit_stage("execute_summary", status="skipped", detail="reason=dry_run_enabled")
            _emit_stage("persist_markdown", status="skipped", detail="reason=dry_run_enabled")
            _emit_stage("persist_metadata", status="skipped", detail="reason=dry_run_enabled")
            return 0

        ocr_responses = _time_stage(lambda: execute_ocr(config, resized_images))
        _emit_stage("execute_ocr", status="ok", detail=f"responses={len(ocr_responses)}")

        summary_attempts = _time_stage(lambda: execute_summaries(config, ocr_responses))
        summary_failures = sum(1 for attempt in summary_attempts if attempt.failed)
        _emit_stage("execute_summary", status="ok", detail=f"responses={len(summary_attempts)} failures={summary_failures}")

        persisted_records = _time_stage(
            lambda: persist_markdown(config, ocr_responses, pdf_pages, resized_images, token_reports)
        )
        _emit_stage("persist_markdown", status="ok", detail=f"records={len(persisted_records)}")

        metadata_records = _time_stage(
            lambda: persist_metadata(config, persisted_records, ocr_responses, summary_attempts)
        )
        _emit_stage("persist_metadata", status="ok", detail=f"records={len(metadata_records)}")
        return 0
    except ConfigValidationError as exc:
        _emit_error(exc.error_code, str(exc))
        return 2
    except TokenBudgetValidationError as exc:
        _emit_error("token_budget_exceeded", str(exc))
        return 3
    except GatewayError as exc:
        _emit_error(exc.error_code, str(exc))
        return 4
    except Exception as exc:
        _emit_error("foundation_runtime_error", f"{type(exc).__name__}: {exc}")
        return 1


def run_phase_one_bootstrap(config: AppConfig) -> int:
    return run_foundation_bootstrap(config)
