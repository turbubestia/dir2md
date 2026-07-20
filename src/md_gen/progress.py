from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


GenerationProgressKind = Literal[
    "stage_start",
    "ocr_item_start",
    "ocr_item_complete",
    "batch_persisted",
    "complete",
    "failed",
]


@dataclass(frozen=True)
class GenerationProgressEvent:
    kind: GenerationProgressKind
    total_jobs: int = 0
    completed_jobs: int = 0
    markdown_count: int = 0
    source_path: Path | None = None
    source_file_name: str | None = None
    source_type: str | None = None
    page_number: int | None = None
    markdown_path: Path | None = None
    error_code: str | None = None
    message: str | None = None


GenerationProgressCallback = Callable[[GenerationProgressEvent], None]


@dataclass
class GenerationProgressContext:
    total_jobs: int
    completed_jobs: int = 0
    markdown_count: int = 0
