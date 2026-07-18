"""Workflow discovery, preview validation, and OCR orchestration."""

from __future__ import annotations

import base64
import json
import queue
import threading
from pathlib import Path
from typing import Any

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
from md_gen import foundation as md_gen_foundation
from md_gen.discovery import build_work_items
from md_gen.progress import GenerationProgressEvent
from md_mrg import planner as md_mrg_planner
from md_mrg.planner import PlannerError, PlanningProgressEvent

from .models import (
    AppSettings,
    FolderStatus,
    FolderStatusKind,
    WorkflowActiveComparison,
    WorkflowActiveItem,
    WorkflowCounts,
    WorkflowDiscoveryResponse,
    WorkflowMetrics,
    WorkflowProgress,
    WorkflowSourceFile,
    WorkflowState,
    WorkflowStatusMessage,
)


class WorkflowServiceError(Exception):
    """Raised when a workflow request is invalid or cannot be served."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class WorkflowService:
    """Owns local workflow state for one webapp process."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = WorkflowState(
            messages=[WorkflowStatusMessage(severity="info", code="idle", message="Start discovery has not run.")]
        )
        self._subscribers: list[queue.Queue[WorkflowState]] = []
        self._worker: threading.Thread | None = None

    def get_state(self) -> WorkflowState:
        with self._lock:
            return self._copy_state()

    def discover_start(self, settings: AppSettings) -> WorkflowDiscoveryResponse:
        discovery = _discover_start(settings)
        with self._lock:
            self._state = WorkflowState(
                discovery=discovery,
                ocr_status="enabled" if discovery.ok and discovery.metrics.total_count > 0 else "idle",
                messages=discovery.messages,
            )
            state = self._copy_state()
        self._broadcast(state)
        return discovery

    def resolve_preview_path(self, settings: AppSettings, file_id: str) -> Path:
        return _resolve_preview_path(settings, file_id)

    def start_ocr(self, settings: AppSettings) -> WorkflowState:
        with self._lock:
            if self._state.ocr_status == "running":
                raise WorkflowServiceError("OCR is already running.", status_code=409)
            discovery = self._state.discovery

        if discovery is None or not discovery.ok or discovery.metrics.total_count <= 0:
            raise WorkflowServiceError("Run Start successfully before OCR.", status_code=400)

        config = _settings_to_runtime_config(settings)

        with self._lock:
            self._state.ocr_status = "running"
            self._state.progress = WorkflowProgress(stage="ocr", total_jobs=0, completed_jobs=0, percent=0.0)
            self._state.counts = WorkflowCounts()
            self._state.current_item = None
            self._state.active_comparison = None
            self._state.completed_item_ids = []
            self._state.error = None
            self._state.messages = [
                WorkflowStatusMessage(severity="info", code="ocr_running", message="OCR generation is running.")
            ]
            state = self._copy_state()
            self._worker = threading.Thread(target=self._run_ocr_worker, args=(config,), daemon=True)
            self._worker.start()
        self._broadcast(state)
        return state

    def subscribe(self) -> queue.Queue[WorkflowState]:
        subscriber: queue.Queue[WorkflowState] = queue.Queue()
        with self._lock:
            self._subscribers.append(subscriber)
            subscriber.put(self._copy_state())
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue[WorkflowState]) -> None:
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

    def _run_ocr_worker(self, config: AppConfig) -> None:
        try:
            exit_code = md_gen_foundation.run_generation(config, progress_callback=self._handle_generation_progress)
            batch_path = config.paths.output_dir / md_mrg_planner.BATCH_FILE_NAME
            if exit_code != 0:
                self._mark_failed("generation_failed", f"OCR generation failed with exit code {exit_code}.")
                return
            if not batch_path.exists():
                self._mark_failed("batch_missing", f"OCR generation did not create {batch_path.name}.")
                return

            self._update_counts_from_batch(batch_path)
            output = md_mrg_planner.run_plan(
                source_dir=config.paths.output_dir,
                cfg=config,
                progress_callback=self._handle_planning_progress,
            )
            if not isinstance(output.get("documents"), list):
                self._mark_failed("plan_invalid", "Merge planning returned an invalid document list.")
                return
            self._update_counts_from_plan(config.paths.output_dir / md_mrg_planner.MERGE_PLAN_FILE_NAME)
            self._mark_complete()
        except PlannerError as exc:
            self._mark_failed(exc.error_code, str(exc))
        except Exception as exc:
            self._mark_failed("workflow_runtime_error", f"{type(exc).__name__}: {exc}")

    def _handle_generation_progress(self, event: GenerationProgressEvent) -> None:
        with self._lock:
            if event.kind == "stage_start":
                self._state.progress = WorkflowProgress(
                    stage="ocr",
                    total_jobs=event.total_jobs,
                    completed_jobs=0,
                    percent=0.0,
                )
            elif event.kind in {"ocr_item_start", "ocr_item_complete"}:
                next_item = _active_item_from_generation_event(self._state.discovery, event)
                if event.kind == "ocr_item_start" and next_item is not None:
                    current_item = self._state.current_item
                    if current_item is not None and current_item.source_id != next_item.source_id:
                        self._add_completed_item_id(current_item.source_id)
                self._state.progress = WorkflowProgress(
                    stage="ocr",
                    total_jobs=event.total_jobs,
                    completed_jobs=event.completed_jobs,
                    percent=_bounded_percent(event.completed_jobs, event.total_jobs, start=0.0, span=50.0),
                )
                self._state.counts.markdown_count = event.markdown_count
                self._state.current_item = next_item
                self._state.active_comparison = None
                if event.kind == "ocr_item_complete" and event.source_type == "image" and next_item is not None:
                    self._add_completed_item_id(next_item.source_id)
                if event.kind == "ocr_item_start" and event.source_file_name:
                    page = f" page {event.page_number}" if event.page_number else ""
                    self._state.messages = [
                        WorkflowStatusMessage(
                            severity="info",
                            code="ocr_item_running",
                            message=f"Processing {event.source_file_name}{page}.",
                        )
                    ]
            elif event.kind == "batch_persisted":
                self._state.progress = WorkflowProgress(
                    stage="planning",
                    total_jobs=event.total_jobs,
                    completed_jobs=event.completed_jobs,
                    percent=50.0,
                )
                self._state.counts.markdown_count = event.markdown_count
                if self._state.current_item is not None:
                    self._add_completed_item_id(self._state.current_item.source_id)
                self._state.current_item = None
            elif event.kind == "failed":
                self._state.error = WorkflowStatusMessage(
                    severity="error",
                    code=event.error_code or "generation_failed",
                    message=event.message or "OCR generation failed.",
                )
                self._state.messages = [self._state.error]
            state = self._copy_state()
        self._broadcast(state)

    def _handle_planning_progress(self, event: PlanningProgressEvent) -> None:
        with self._lock:
            percent = _bounded_percent(
                event.completed_comparisons,
                event.total_comparisons,
                start=50.0,
                span=50.0,
                zero_value=100.0,
            )
            self._state.progress = WorkflowProgress(
                stage="planning",
                total_jobs=event.total_comparisons,
                completed_jobs=event.completed_comparisons,
                percent=percent,
            )
            self._state.counts.pdf_document_count = event.pdf_document_count
            if event.image_group_count:
                self._state.counts.image_group_count = event.image_group_count
            self._state.current_item = None
            if event.kind == "comparison_start":
                self._state.active_comparison = WorkflowActiveComparison(
                    left_source_id=_source_id_from_display_name(self._state.discovery, event.left_display_name),
                    right_source_id=_source_id_from_display_name(self._state.discovery, event.right_display_name),
                    left_display_name=event.left_display_name,
                    right_display_name=event.right_display_name,
                )
                if event.left_display_name and event.right_display_name:
                    self._state.messages = [
                        WorkflowStatusMessage(
                            severity="info",
                            code="planning_comparison_running",
                            message=f"Comparing {event.left_display_name} with {event.right_display_name}.",
                        )
                    ]
            elif event.kind in {"plan_persisted", "complete"}:
                self._state.active_comparison = None
            elif event.kind == "failed":
                self._state.error = WorkflowStatusMessage(
                    severity="error",
                    code=event.error_code or "planning_failed",
                    message=event.message or "Merge planning failed.",
                )
                self._state.messages = [self._state.error]
            state = self._copy_state()
        self._broadcast(state)

    def _update_counts_from_batch(self, batch_path: Path) -> None:
        payload = _read_json(batch_path)
        documents = payload.get("documents", [])
        if not isinstance(documents, list):
            raise WorkflowServiceError("batch.json has an invalid documents field.")
        pdf_document_count = sum(1 for item in documents if isinstance(item, dict) and item.get("file_type") == "pdf")
        with self._lock:
            self._state.counts.pdf_document_count = pdf_document_count
            state = self._copy_state()
        self._broadcast(state)

    def _update_counts_from_plan(self, plan_path: Path) -> None:
        payload = _read_json(plan_path)
        documents = payload.get("documents", [])
        if not isinstance(documents, list):
            raise WorkflowServiceError("batch_mrg.json has an invalid documents field.")
        image_group_count = sum(1 for item in documents if isinstance(item, dict) and isinstance(item.get("documents"), list))
        with self._lock:
            self._state.counts.image_group_count = image_group_count
            state = self._copy_state()
        self._broadcast(state)

    def _mark_failed(self, code: str, message: str) -> None:
        with self._lock:
            error = WorkflowStatusMessage(severity="error", code=code, message=message)
            self._state.ocr_status = "failed"
            self._state.error = error
            self._state.messages = [error]
            self._state.current_item = None
            self._state.active_comparison = None
            state = self._copy_state()
        self._broadcast(state)

    def _mark_complete(self) -> None:
        with self._lock:
            self._state.ocr_status = "complete"
            self._state.progress = WorkflowProgress(stage="planning", total_jobs=0, completed_jobs=0, percent=100.0)
            self._state.current_item = None
            self._state.active_comparison = None
            self._state.completed_item_ids = _merge_unique_ids(
                self._state.completed_item_ids,
                _all_discovered_item_ids(self._state.discovery),
            )
            self._state.error = None
            self._state.messages = [
                WorkflowStatusMessage(severity="success", code="ocr_complete", message="OCR and planning completed.")
            ]
            state = self._copy_state()
        self._broadcast(state)

    def _broadcast(self, state: WorkflowState) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber.put(state)

    def _copy_state(self) -> WorkflowState:
        return self._state.model_copy(deep=True)

    def _add_completed_item_id(self, source_id: str | None) -> None:
        if source_id is not None and source_id not in self._state.completed_item_ids:
            self._state.completed_item_ids.append(source_id)


def discover_start(settings: AppSettings) -> WorkflowDiscoveryResponse:
    """Compatibility wrapper for tests and direct callers."""
    return _discover_start(settings)


def resolve_preview_path(settings: AppSettings, file_id: str) -> Path:
    """Compatibility wrapper for tests and direct callers."""
    return _resolve_preview_path(settings, file_id)


def _discover_start(settings: AppSettings) -> WorkflowDiscoveryResponse:
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
        work_items = build_work_items(_settings_to_discovery_config(settings, source_dir))
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
            messages=[WorkflowStatusMessage(severity="error", code="source_inaccessible", message=str(exc))],
        )

    items = [_source_file_from_work_item(item, source_dir) for item in work_items]
    pdf_count = sum(1 for item in work_items if item.source_type == "pdf")
    image_count = sum(1 for item in work_items if item.source_type == "image")

    return WorkflowDiscoveryResponse(
        ok=True,
        source_status=source_status,
        output_status=output_status,
        metrics=WorkflowMetrics(pdf_count=pdf_count, image_count=image_count, total_count=len(items)),
        items=items,
        messages=[_discovery_message(source_status.status, len(items))],
    )


def _resolve_preview_path(settings: AppSettings, file_id: str) -> Path:
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
        raise WorkflowServiceError("Preview id is outside the configured source folder.") from exc

    if not candidate.exists() or not candidate.is_file():
        raise WorkflowServiceError("Preview file was not found.", status_code=404)

    try:
        work_items = build_work_items(_settings_to_discovery_config(settings, source_dir))
    except OSError as exc:
        raise WorkflowServiceError("Source folder cannot be read.", status_code=404) from exc

    for item in work_items:
        if item.source_path == candidate:
            return candidate

    raise WorkflowServiceError("Preview file is not a supported source item.", status_code=404)


def _inspect_source_folder(raw_path: str) -> tuple[FolderStatus, Path | None]:
    status, resolved_path = _inspect_optional_folder(raw_path, label="Source")
    if status.status not in {"empty", "ready"}:
        return status, None
    return status, resolved_path


def _inspect_optional_folder(raw_path: str, *, label: str) -> tuple[FolderStatus, Path | None]:
    if not raw_path.strip():
        return (FolderStatus(path="", status="not_configured", message=f"{label} folder is not configured."), None)

    try:
        resolved = Path(raw_path).expanduser().resolve()
        if not resolved.exists():
            return (
                FolderStatus(path=str(resolved), status="missing", message=f"{label} folder does not exist: {resolved}"),
                None,
            )
        if not resolved.is_dir():
            return (
                FolderStatus(path=str(resolved), status="not_directory", message=f"{label} path is not a directory: {resolved}"),
                None,
            )
        item_count = sum(1 for _ in resolved.iterdir())
    except OSError:
        fallback_path = raw_path if raw_path else ""
        return (
            FolderStatus(path=fallback_path, status="inaccessible", message=f"{label} folder cannot be accessed: {fallback_path}"),
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


def _settings_to_discovery_config(settings: AppSettings, source_dir: Path) -> AppConfig:
    prompt = PromptSettings(summary_prompt_path=None, summary_prompt_text="")
    return AppConfig(
        paths=PathSettings(source_dir=source_dir, output_dir=Path(settings.output_folder).expanduser()),
        ocr_model=_model_settings(settings.ocr_model),
        language_model=_model_settings(settings.language_model),
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


def _settings_to_runtime_config(settings: AppSettings) -> AppConfig:
    source_status, source_dir = _inspect_source_folder(settings.source_folder)
    if source_dir is None:
        raise WorkflowServiceError(source_status.message, status_code=400)
    if not settings.output_folder.strip():
        raise WorkflowServiceError("Output folder is not configured.", status_code=400)
    output_dir = Path(settings.output_folder).expanduser().resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkflowServiceError(f"Output folder cannot be created: {output_dir}", status_code=400) from exc
    if not output_dir.is_dir():
        raise WorkflowServiceError(f"Output path is not a directory: {output_dir}", status_code=400)

    return AppConfig(
        paths=PathSettings(source_dir=source_dir, output_dir=output_dir),
        ocr_model=_model_settings(settings.ocr_model),
        language_model=_model_settings(settings.language_model),
        md_gen=ConfigMdGenSettings(
            prompts=_read_prompt(settings.md_gen.summary.prompt_path, "summary"),
            image=ImageSettings(
                max_longest_edge_px=settings.md_gen.image.max_longest_edge_px,
                token_threshold=settings.md_gen.image.token_threshold,
            ),
        ),
        md_mrg=ConfigMdMrgSettings(score=_read_prompt(settings.md_mrg.score.prompt_path, "score")),
        runtime=RuntimeSettings(dry_run=False, overwrite=settings.overwrite),
    )


def _model_settings(model: Any) -> LlamaModelSettings:
    return LlamaModelSettings(
        endpoint_url=str(model.endpoint),
        model_name=model.model,
        request_timeout_seconds=model.timeout_seconds,
        request_max_retries=model.max_retries,
    )


def _read_prompt(raw_path: str, label: str) -> PromptSettings:
    prompt_path = Path(raw_path).expanduser().resolve()
    try:
        text = prompt_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise WorkflowServiceError(f"Failed to read {label} prompt file: {prompt_path}", status_code=400) from exc
    if not text.strip():
        raise WorkflowServiceError(f"{label.capitalize()} prompt file is empty: {prompt_path}", status_code=400)
    return PromptSettings(summary_prompt_path=prompt_path, summary_prompt_text=text)


def _source_file_from_work_item(item, source_dir: Path) -> WorkflowSourceFile:
    relative_path = item.source_path.relative_to(source_dir)
    file_id = _encode_file_id(relative_path)
    return WorkflowSourceFile(
        id=file_id,
        display_name=item.source_path.name,
        absolute_path=str(item.source_path),
        extension=item.source_path.suffix.lower(),
        size_bytes=item.source_path.stat().st_size,
        source_type=item.source_type,
        order_index=item.order_index,
        preview_url=f"/api/workflow/source-preview/{file_id}",
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
        return WorkflowStatusMessage(severity="warning", code="source_empty", message="Source folder is empty.")
    return WorkflowStatusMessage(
        severity="success",
        code="sources_discovered",
        message=f"Discovered {total_count} supported source file(s).",
    )


def _bounded_percent(
    completed: int,
    total: int,
    *,
    start: float,
    span: float,
    zero_value: float | None = None,
) -> float:
    if total <= 0:
        return zero_value if zero_value is not None else start
    return max(start, min(start + span, start + (completed / total) * span))


def _active_item_from_generation_event(
    discovery: WorkflowDiscoveryResponse | None,
    event: GenerationProgressEvent,
) -> WorkflowActiveItem | None:
    if not event.source_file_name:
        return None
    source_id = _source_id_from_path(discovery, event.source_path) or _source_id_from_display_name(discovery, event.source_file_name)
    markdown_file = event.markdown_path.name if event.markdown_path is not None else None
    source_type = event.source_type if event.source_type in {"pdf", "image"} else None
    return WorkflowActiveItem(
        source_id=source_id,
        display_name=event.source_file_name,
        source_type=source_type,
        page_number=event.page_number,
        markdown_file=markdown_file,
    )


def _source_id_from_path(discovery: WorkflowDiscoveryResponse | None, source_path: Path | None) -> str | None:
    if discovery is None or source_path is None:
        return None
    source_path_str = str(source_path)
    for item in discovery.items:
        if item.absolute_path == source_path_str:
            return item.id
    return None


def _source_id_from_display_name(discovery: WorkflowDiscoveryResponse | None, display_name: str | None) -> str | None:
    if discovery is None or not display_name:
        return None
    for item in discovery.items:
        if item.display_name == display_name:
            return item.id
    return None


def _all_discovered_item_ids(discovery: WorkflowDiscoveryResponse | None) -> list[str]:
    if discovery is None:
        return []
    return [item.id for item in discovery.items]


def _merge_unique_ids(left: list[str], right: list[str]) -> list[str]:
    merged = list(left)
    for item_id in right:
        if item_id not in merged:
            merged.append(item_id)
    return merged


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowServiceError(f"Failed to read workflow JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise WorkflowServiceError(f"Workflow JSON file must contain an object: {path}")
    return payload