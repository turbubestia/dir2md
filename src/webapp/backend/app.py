"""FastAPI application for the dir2md webapp.

This module exposes a small settings-only API for the browser UI. It does not
invoke ``md_gen`` or ``md_mrg``; those remain CLI responsibilities.
"""

from __future__ import annotations

import json
import queue
from pathlib import Path
from typing import Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .models import AppSettings, WorkflowDiscoveryResponse, WorkflowState
from .settings_store import (
    DEFAULT_SETTINGS_FILE,
    SETTINGS_FILE,
    SettingsStoreError,
    load_settings,
    save_settings,
)
from .workflow import WorkflowService, WorkflowServiceError


DEFAULT_ALLOWED_ORIGINS: Sequence[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def create_app(
    settings_path: Path = SETTINGS_FILE,
    defaults_path: Path = DEFAULT_SETTINGS_FILE,
    allowed_origins: Sequence[str] | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters may be overridden for tests so filesystem state and CORS
    behavior can be controlled deterministically.
    """
    application = FastAPI(
        title="dir2md webapp",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    origins = list(allowed_origins if allowed_origins is not None else DEFAULT_ALLOWED_ORIGINS)
    workflow_service = WorkflowService()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/settings")
    def get_settings() -> AppSettings:
        try:
            return load_settings(settings_path, defaults_path)
        except SettingsStoreError as exc:
            return JSONResponse(
                status_code=500,
                content={"detail": str(exc)},
            )  # type: ignore[return-value]

    @application.put("/api/settings")
    def put_settings(payload: AppSettings) -> AppSettings:
        try:
            saved = save_settings(payload, settings_path)
            return saved
        except SettingsStoreError as exc:
            return JSONResponse(
                status_code=500,
                content={"detail": str(exc)},
            )  # type: ignore[return-value]

    @application.post("/api/workflow/start")
    def post_workflow_start() -> WorkflowDiscoveryResponse:
        try:
            settings = load_settings(settings_path, defaults_path)
            return workflow_service.discover_start(settings)
        except SettingsStoreError as exc:
            return JSONResponse(
                status_code=500,
                content={"detail": str(exc)},
            )  # type: ignore[return-value]

    @application.post("/api/workflow/ocr")
    def post_workflow_ocr() -> WorkflowState:
        try:
            settings = load_settings(settings_path, defaults_path)
            return workflow_service.start_ocr(settings)
        except SettingsStoreError as exc:
            return JSONResponse(
                status_code=500,
                content={"detail": str(exc)},
            )  # type: ignore[return-value]
        except WorkflowServiceError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": str(exc)},
            )  # type: ignore[return-value]

    @application.get("/api/workflow/state")
    def get_workflow_state() -> WorkflowState:
        return workflow_service.get_state()

    @application.get("/api/workflow/events")
    def get_workflow_events(once: bool = False) -> StreamingResponse:
        subscriber = workflow_service.subscribe()

        def stream():
            try:
                while True:
                    try:
                        state = subscriber.get(timeout=0.25)
                    except queue.Empty:
                        continue
                    payload = json.dumps(state.model_dump(mode="json"), ensure_ascii=False)
                    yield f"event: workflow_state\ndata: {payload}\n\n"
                    if once:
                        break
            finally:
                workflow_service.unsubscribe(subscriber)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @application.get("/api/workflow/source-preview/{file_id}")
    def get_source_preview(file_id: str) -> FileResponse:
        try:
            settings = load_settings(settings_path, defaults_path)
            path = workflow_service.resolve_preview_path(settings, file_id)
            return FileResponse(path)
        except SettingsStoreError as exc:
            return JSONResponse(
                status_code=500,
                content={"detail": str(exc)},
            )  # type: ignore[return-value]
        except WorkflowServiceError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": str(exc)},
            )  # type: ignore[return-value]

    return application


app = create_app()
