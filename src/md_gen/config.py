from __future__ import annotations

import os
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
class OcrModelSettings:
    endpoint_url: str
    model_name: str
    request_timeout_seconds: float
    request_max_retries: int


@dataclass(frozen=True)
class SummaryModelSettings:
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
    ocr_model: OcrModelSettings
    summary_model: SummaryModelSettings
    image: ImageSettings
    runtime: RuntimeSettings


def _normalize_paths(raw_paths: list[str] | None) -> tuple[Path, ...]:
    if not raw_paths:
        return tuple()
    normalized = sorted({Path(path).expanduser().resolve() for path in raw_paths})
    return tuple(normalized)


def _source_base_path(source_path: Path) -> Path:
    if source_path.exists():
        return source_path if source_path.is_dir() else source_path.parent
    if source_path.suffix:
        return source_path.parent
    return source_path


def _resolve_default_base_dir(source_paths: tuple[Path, ...], source_list_files: tuple[Path, ...]) -> Path:
    if source_paths:
        source_bases = [_source_base_path(source_path) for source_path in source_paths]
        if len(source_bases) == 1:
            return source_bases[0]
        common = os.path.commonpath([base.as_posix() for base in source_bases])
        return Path(common)

    if source_list_files:
        list_bases = [list_file.parent for list_file in source_list_files]
        if len(list_bases) == 1:
            return list_bases[0]
        common = os.path.commonpath([base.as_posix() for base in list_bases])
        return Path(common)

    return Path.cwd().resolve()


def _resolve_optional_path(raw_value: str | None, fallback: Path) -> Path:
    if raw_value is None:
        return fallback.resolve()
    return Path(raw_value).expanduser().resolve()


def _arg_with_fallback(args: SimpleNamespace, preferred: str, fallback: str) -> str:
    preferred_value = getattr(args, preferred, None)
    if preferred_value is not None:
        return str(preferred_value)
    fallback_value = getattr(args, fallback, None)
    if fallback_value is not None:
        return str(fallback_value)
    raise AttributeError(f"Missing required argument values: {preferred} and {fallback}")


def build_config_from_args(args: SimpleNamespace) -> AppConfig:
    source_paths = _normalize_paths(args.source)
    source_list_files = _normalize_paths(args.source_list_file)
    base_dir = _resolve_default_base_dir(source_paths=source_paths, source_list_files=source_list_files)
    return AppConfig(
        paths=PathSettings(
            source_paths=source_paths,
            source_list_files=source_list_files,
            output_dir=_resolve_optional_path(args.output_dir, base_dir / "output"),
            im_temp_dir=_resolve_optional_path(args.im_temp_dir, base_dir / "im-temp"),
            md_temp_dir=_resolve_optional_path(args.md_temp_dir, base_dir / "md-temp"),
            log_file=_resolve_optional_path(args.log_file, base_dir / "logs" / "md-gen.log"),
        ),
        ocr_model=OcrModelSettings(
            endpoint_url=_arg_with_fallback(args, "ocr_model_endpoint_url", "model_endpoint_url"),
            model_name=_arg_with_fallback(args, "ocr_model_name", "model_name"),
            request_timeout_seconds=float(
                _arg_with_fallback(args, "ocr_request_timeout_seconds", "request_timeout_seconds")
            ),
            request_max_retries=int(_arg_with_fallback(args, "ocr_request_max_retries", "request_max_retries")),
        ),
        summary_model=SummaryModelSettings(
            endpoint_url=getattr(args, "summary_model_endpoint_url", "http://localhost:8081/v1/chat/completions"),
            model_name=getattr(args, "summary_model_name", "qwen3-1.7b"),
            request_timeout_seconds=getattr(args, "summary_request_timeout_seconds", 120.0),
            request_max_retries=getattr(args, "summary_request_max_retries", 2),
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
