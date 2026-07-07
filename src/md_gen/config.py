from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace


@dataclass(frozen=True)
class PathSettings:
    source_paths: tuple[Path, ...]
    source_list_files: tuple[Path, ...]
    output_dir: Path
    im_temp_dir: Path
    md_temp_dir: Path
    log_file: Path


@dataclass(frozen=True)
class ModelSettings:
    endpoint_url: str
    model_name: str
    request_timeout_seconds: float
    request_max_retries: int


@dataclass(frozen=True)
class ImageSettings:
    max_longest_edge_px: int
    token_threshold: int


@dataclass(frozen=True)
class RuntimeSettings:
    dry_run: bool
    overwrite: bool


@dataclass(frozen=True)
class AppConfig:
    paths: PathSettings
    model: ModelSettings
    image: ImageSettings
    runtime: RuntimeSettings


def _normalize_paths(raw_paths: list[str] | None) -> tuple[Path, ...]:
    if not raw_paths:
        return tuple()
    normalized = sorted({Path(path).expanduser().resolve() for path in raw_paths})
    return tuple(normalized)


def build_config_from_args(args: SimpleNamespace) -> AppConfig:
    source_paths = _normalize_paths(args.source)
    source_list_files = _normalize_paths(args.source_list_file)
    return AppConfig(
        paths=PathSettings(
            source_paths=source_paths,
            source_list_files=source_list_files,
            output_dir=Path(args.output_dir).expanduser().resolve(),
            im_temp_dir=Path(args.im_temp_dir).expanduser().resolve(),
            md_temp_dir=Path(args.md_temp_dir).expanduser().resolve(),
            log_file=Path(args.log_file).expanduser().resolve(),
        ),
        model=ModelSettings(
            endpoint_url=args.model_endpoint_url,
            model_name=args.model_name,
            request_timeout_seconds=args.request_timeout_seconds,
            request_max_retries=args.request_max_retries,
        ),
        image=ImageSettings(
            max_longest_edge_px=args.max_longest_edge_px,
            token_threshold=args.token_threshold,
        ),
        runtime=RuntimeSettings(
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        ),
    )
