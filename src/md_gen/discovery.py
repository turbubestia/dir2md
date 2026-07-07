from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .config import AppConfig

SourceType = Literal["pdf", "image"]

_PDF_EXTENSIONS = {".pdf"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
_SUPPORTED_EXTENSIONS = _PDF_EXTENSIONS | _IMAGE_EXTENSIONS


@dataclass(frozen=True)
class WorkItem:
    source_path: Path
    source_type: SourceType
    order_index: int
    ordering_key: str


def _ordering_key(path: Path) -> str:
    return path.as_posix().lower()


def _iter_paths_from_list_file(list_file_path: Path) -> list[Path]:
    candidates: list[Path] = []
    base_dir = list_file_path.parent
    for raw_line in list_file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parsed = Path(line).expanduser()
        if not parsed.is_absolute():
            parsed = (base_dir / parsed).resolve()
        else:
            parsed = parsed.resolve()
        candidates.append(parsed)
    return candidates


def _collect_candidate_paths(config: AppConfig) -> list[Path]:
    candidates = list(config.paths.source_paths)
    for list_file_path in config.paths.source_list_files:
        candidates.extend(_iter_paths_from_list_file(list_file_path))
    return candidates


def _discover_from_path(path: Path) -> list[Path]:
    if path.is_dir():
        return [
            candidate.resolve()
            for candidate in sorted(path.rglob("*"), key=lambda candidate: _ordering_key(candidate.resolve()))
            if candidate.is_file() and candidate.suffix.lower() in _SUPPORTED_EXTENSIONS
        ]

    if not path.exists():
        raise FileNotFoundError(f"Input path does not exist: {path}")

    if path.is_file() and path.suffix.lower() in _SUPPORTED_EXTENSIONS:
        return [path.resolve()]

    return []


def discover_supported_files(config: AppConfig) -> tuple[Path, ...]:
    discovered: set[Path] = set()
    for candidate in _collect_candidate_paths(config):
        discovered.update(_discover_from_path(candidate))

    ordered = sorted(discovered, key=_ordering_key)
    return tuple(ordered)


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