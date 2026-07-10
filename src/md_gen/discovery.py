from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .config import AppConfig

SourceType = Literal["pdf", "image"]

_PDF_EXTENSIONS = {".pdf"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpge"}
_SUPPORTED_EXTENSIONS = _PDF_EXTENSIONS | _IMAGE_EXTENSIONS
_DISCOVERY_PREFIX = "DISCOVERY"


@dataclass(frozen=True)
class WorkItem:
    source_path: Path
    source_type: SourceType
    order_index: int
    ordering_key: str


def _ordering_key(path: Path) -> str:
    return path.as_posix().lower()


def _print_discovery_status(path: Path, *, status: str, reason: str = "") -> None:
    reason_token = f" reason={reason}" if reason else ""
    print(f"{_DISCOVERY_PREFIX} status={status} path={path.resolve()}{reason_token}")


def _is_supported_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in _SUPPORTED_EXTENSIONS


def discover_supported_files(config: AppConfig) -> tuple[Path, ...]:
    discovered: list[Path] = []
    entries = sorted(config.paths.source_dir.iterdir(), key=lambda candidate: _ordering_key(candidate.resolve()))
    for entry in entries:
        resolved = entry.resolve()
        if _is_supported_file(resolved):
            _print_discovery_status(resolved, status="consumed")
            discovered.append(resolved)
            continue

        if entry.is_dir():
            _print_discovery_status(resolved, status="skipped", reason="not_a_file")
            continue

        _print_discovery_status(resolved, status="skipped", reason="unsupported_extension")

    return tuple(discovered)


def _source_type_for_file(path: Path) -> SourceType:
    suffix = path.suffix.lower()
    if suffix in _PDF_EXTENSIONS:
        return "pdf"
    return "image"


def normalize_work_items(files: tuple[Path, ...]) -> tuple[WorkItem, ...]:
    return tuple(
        WorkItem(
            source_path=path,
            source_type=_source_type_for_file(path),
            order_index=index,
            ordering_key=_ordering_key(path),
        )
        for index, path in enumerate(files)
    )


def build_work_items(config: AppConfig) -> tuple[WorkItem, ...]:
    discovered_files = discover_supported_files(config)
    return normalize_work_items(discovered_files)