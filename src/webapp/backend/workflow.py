"""Workflow discovery and preview validation for the webapp backend."""

from __future__ import annotations

import base64
from pathlib import Path

from common.config import (
    AppConfig,
    ImageSettings,
    LlamaModelSettings,
    MdGenSettings as ConfigMdGenSettings,
    MdMrgSettings as ConfigMdMrgSettings,
    PathSettings,
    PromptSettings,
    RuntimeSettings,
)
from md_gen.discovery import build_work_items

from .models import (
    AppSettings,
    FolderStatus,
    FolderStatusKind,
    WorkflowDiscoveryResponse,
    WorkflowMetrics,
    WorkflowSourceFile,
    WorkflowStatusMessage,
)


class WorkflowServiceError(Exception):
    """Raised when a preview request is invalid or cannot be served."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def discover_start(settings: AppSettings) -> WorkflowDiscoveryResponse:
    """Discover supported source files for the workflow Start stage."""
    source_status, source_dir = _inspect_source_folder(settings.source_folder)
    output_status, _ = _inspect_optional_folder(settings.output_folder, label="Output")

    if source_dir is None:
        return WorkflowDiscoveryResponse(
            ok=False,
            source_status=source_status,
            output_status=output_status,
            metrics=WorkflowMetrics(pdf_count=0, image_count=0, total_count=0),
            items=[],
            messages=[
                WorkflowStatusMessage(
                    severity="error",
                    code=f"source_{source_status.status}",
                    message=source_status.message,
                )
            ],
        )

    try:
        work_items = build_work_items(_settings_to_config(settings, source_dir))
    except OSError as exc:
        status = FolderStatus(
            path=str(source_dir),
            status="inaccessible",
            message=f"Source folder cannot be read: {source_dir}",
        )
        return WorkflowDiscoveryResponse(
            ok=False,
            source_status=status,
            output_status=output_status,
            metrics=WorkflowMetrics(pdf_count=0, image_count=0, total_count=0),
            items=[],
            messages=[
                WorkflowStatusMessage(
                    severity="error",
                    code="source_inaccessible",
                    message=str(exc),
                )
            ],
        )

    items = [_source_file_from_work_item(item, source_dir) for item in work_items]
    pdf_count = sum(1 for item in work_items if item.source_type == "pdf")
    image_count = sum(1 for item in work_items if item.source_type == "image")
    messages = [_discovery_message(source_status.status, len(items))]

    return WorkflowDiscoveryResponse(
        ok=True,
        source_status=source_status,
        output_status=output_status,
        metrics=WorkflowMetrics(
            pdf_count=pdf_count,
            image_count=image_count,
            total_count=len(items),
        ),
        items=items,
        messages=messages,
    )


def resolve_preview_path(settings: AppSettings, file_id: str) -> Path:
    """Resolve and validate a source image preview path for the current settings."""
    source_status, source_dir = _inspect_source_folder(settings.source_folder)
    if source_dir is None:
        raise WorkflowServiceError(source_status.message, status_code=404)

    relative_path = _decode_file_id(file_id)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise WorkflowServiceError("Preview id is outside the configured source folder.")

    try:
        candidate = (source_dir / relative_path).resolve()
        candidate.relative_to(source_dir)
    except (OSError, ValueError) as exc:
        raise WorkflowServiceError(
            "Preview id is outside the configured source folder."
        ) from exc

    if not candidate.exists() or not candidate.is_file():
        raise WorkflowServiceError("Preview file was not found.", status_code=404)

    try:
        work_items = build_work_items(_settings_to_config(settings, source_dir))
    except OSError as exc:
        raise WorkflowServiceError(
            "Source folder cannot be read.", status_code=404
        ) from exc

    for item in work_items:
        if item.source_path == candidate:
            if item.source_type != "image":
                raise WorkflowServiceError("Preview is only available for image sources.")
            return candidate

    raise WorkflowServiceError("Preview file is not a supported source item.", status_code=404)


def _inspect_source_folder(raw_path: str) -> tuple[FolderStatus, Path | None]:
    status, resolved_path = _inspect_optional_folder(raw_path, label="Source")
    if status.status not in {"empty", "ready"}:
        return status, None
    return status, resolved_path


def _inspect_optional_folder(raw_path: str, *, label: str) -> tuple[FolderStatus, Path | None]:
    if not raw_path.strip():
        return (
            FolderStatus(
                path="",
                status="not_configured",
                message=f"{label} folder is not configured.",
            ),
            None,
        )

    try:
        resolved = Path(raw_path).expanduser().resolve()
        if not resolved.exists():
            return (
                FolderStatus(
                    path=str(resolved),
                    status="missing",
                    message=f"{label} folder does not exist: {resolved}",
                ),
                None,
            )
        if not resolved.is_dir():
            return (
                FolderStatus(
                    path=str(resolved),
                    status="not_directory",
                    message=f"{label} path is not a directory: {resolved}",
                ),
                None,
            )
        item_count = sum(1 for _ in resolved.iterdir())
    except OSError:
        fallback_path = raw_path if raw_path else ""
        return (
            FolderStatus(
                path=fallback_path,
                status="inaccessible",
                message=f"{label} folder cannot be accessed: {fallback_path}",
            ),
            None,
        )

    status: FolderStatusKind = "empty" if item_count == 0 else "ready"
    return (
        FolderStatus(
            path=str(resolved),
            status=status,
            message=f"{label} folder is {status.replace('_', ' ')}.",
            item_count=item_count,
        ),
        resolved,
    )


def _settings_to_config(settings: AppSettings, source_dir: Path) -> AppConfig:
    prompt = PromptSettings(summary_prompt_path=None, summary_prompt_text="")
    return AppConfig(
        paths=PathSettings(
            source_dir=source_dir,
            output_dir=Path(settings.output_folder).expanduser(),
        ),
        ocr_model=LlamaModelSettings(
            endpoint_url=str(settings.ocr_model.endpoint),
            model_name=settings.ocr_model.model,
            request_timeout_seconds=settings.ocr_model.timeout_seconds,
            request_max_retries=settings.ocr_model.max_retries,
        ),
        language_model=LlamaModelSettings(
            endpoint_url=str(settings.language_model.endpoint),
            model_name=settings.language_model.model,
            request_timeout_seconds=settings.language_model.timeout_seconds,
            request_max_retries=settings.language_model.max_retries,
        ),
        md_gen=ConfigMdGenSettings(
            prompts=prompt,
            image=ImageSettings(
                max_longest_edge_px=settings.md_gen.image.max_longest_edge_px,
                token_threshold=settings.md_gen.image.token_threshold,
            ),
        ),
        md_mrg=ConfigMdMrgSettings(score=prompt),
        runtime=RuntimeSettings(dry_run=True, overwrite=settings.overwrite),
    )


def _source_file_from_work_item(item, source_dir: Path) -> WorkflowSourceFile:
    relative_path = item.source_path.relative_to(source_dir)
    file_id = _encode_file_id(relative_path)
    preview_url = (
        f"/api/workflow/source-preview/{file_id}"
        if item.source_type == "image"
        else None
    )
    return WorkflowSourceFile(
        id=file_id,
        display_name=item.source_path.name,
        absolute_path=str(item.source_path),
        extension=item.source_path.suffix.lower(),
        size_bytes=item.source_path.stat().st_size,
        source_type=item.source_type,
        order_index=item.order_index,
        preview_url=preview_url,
    )


def _encode_file_id(relative_path: Path) -> str:
    raw = relative_path.as_posix().encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_file_id(file_id: str) -> Path:
    try:
        padding = "=" * (-len(file_id) % 4)
        decoded = base64.urlsafe_b64decode(f"{file_id}{padding}").decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise WorkflowServiceError("Preview id is invalid.") from exc

    if not decoded:
        raise WorkflowServiceError("Preview id is invalid.")
    return Path(decoded)


def _discovery_message(source_status: FolderStatusKind, total_count: int) -> WorkflowStatusMessage:
    if total_count == 0:
        return WorkflowStatusMessage(
            severity="warning",
            code="no_supported_sources",
            message="No supported PDF or image files were found in the source folder.",
        )
    if source_status == "empty":
        return WorkflowStatusMessage(
            severity="warning",
            code="source_empty",
            message="Source folder is empty.",
        )
    return WorkflowStatusMessage(
        severity="success",
        code="sources_discovered",
        message=f"Discovered {total_count} supported source file(s).",
    )