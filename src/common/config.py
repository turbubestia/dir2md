from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping


class ConfigValidationError(ValueError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


DEFAULT_SETTINGS_FILE = Path(__file__).resolve().parents[2] / "data" / "config" / "settings.json"
DEFAULT_SUMMARY_PROMPT_FILE = Path(__file__).resolve().parents[2] / "data" / "prompts" / "md_gen_summary_system_prompt.md"
DEFAULT_SCORE_PROMPT_FILE = Path(__file__).resolve().parents[2] / "data" / "prompts" / "md_mrg_score_system_prompt.md"

_MISSING = object()


@dataclass(frozen=True)
class PathSettings:
    source_dir: Path | None = None
    output_dir: Path | None = None


@dataclass(frozen=True)
class PromptSettings:
    summary_prompt_path: Path | None = None
    summary_prompt_text: str | None = None


@dataclass(frozen=False)
class LlamaModelSettings:
    endpoint_url: str | None = None
    model_name: str | None = None
    request_timeout_seconds: float = 120.0
    request_max_retries: int = 3
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 0
    min_p: float = 0.05


@dataclass(frozen=True)
class ImageSettings:
    max_longest_edge_px: int = 1540
    token_threshold: int = 4096


@dataclass(frozen=True)
class RuntimeSettings:
    dry_run: bool = False
    overwrite: bool = False
    verbose: bool = False


@dataclass(frozen=True)
class MdGenSettings:
    prompts: PromptSettings
    image: ImageSettings


@dataclass(frozen=True)
class MdMrgSettings:
    score: PromptSettings


@dataclass(frozen=True)
class AppConfig:
    paths: PathSettings
    ocr_model: LlamaModelSettings
    language_model: LlamaModelSettings
    md_gen: MdGenSettings
    md_mrg: MdMrgSettings
    runtime: RuntimeSettings


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _nested_get(document: Mapping[str, Any] | None, *path: str) -> Any:
    current: Any = document
    for key in path:
        if not isinstance(current, Mapping):
            return _MISSING
        current = current.get(key, _MISSING)
        if current is _MISSING:
            return _MISSING
    return current


def _coerce_path(value: Any) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value.expanduser().resolve()
    if isinstance(value, str) and value.strip():
        return Path(value).expanduser().resolve()
    return None


def _coerce_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _warn_default(field_name: str, value: Any) -> None:
    warnings.warn(f"Using default for {field_name}: {value}", RuntimeWarning, stacklevel=3)


def _load_settings_document(settings_path: Path = DEFAULT_SETTINGS_FILE) -> dict[str, Any]:
    try:
        with settings_path.open("r", encoding="utf-8") as file_handle:
            payload = json.load(file_handle)
    except (OSError, json.JSONDecodeError):
        return {}

    if isinstance(payload, dict):
        return payload
    return {}


def read_json_settings_file() -> dict[str, Any]:
    return _load_settings_document(DEFAULT_SETTINGS_FILE)


def _normalize_settings_document(raw_settings: Mapping[str, Any] | None) -> dict[str, Any]:
    settings = _as_mapping(raw_settings)

    normalized_paths = _as_mapping(settings.get("paths"))
    if not normalized_paths:
        normalized_paths = {
            "source_dir": settings.get("source_folder"),
            "output_dir": settings.get("output_folder"),
        }

    normalized_runtime = _as_mapping(settings.get("runtime"))
    if not normalized_runtime:
        normalized_runtime = {
            "dry_run": settings.get("dry_run"),
            "overwrite": settings.get("overwrite"),
            "verbose": settings.get("verbose"),
        }

    return {
        "paths": normalized_paths,
        "ocr_model": _as_mapping(settings.get("ocr_model")),
        "language_model": _as_mapping(settings.get("language_model")),
        "md_gen": _as_mapping(settings.get("md_gen")),
        "md_mrg": _as_mapping(settings.get("md_mrg")),
        "runtime": normalized_runtime,
    }


def _resolve_tiered_value(
    *,
    field_name: str,
    override_value: Any,
    settings_value: Any,
    default_value: Any = _MISSING,
    parser: Any,
) -> Any:
    parsed_override = parser(override_value)
    if parsed_override is not None:
        return parsed_override

    parsed_settings = parser(settings_value)
    if parsed_settings is not None:
        return parsed_settings

    if default_value is not _MISSING:
        _warn_default(field_name, default_value)
        return default_value

    return None


def _resolve_paths_settings(overrides: Mapping[str, Any] | None, settings: Mapping[str, Any] | None) -> PathSettings:
    override_paths = _as_mapping(overrides)
    settings_paths = _as_mapping(settings)
    return PathSettings(
        source_dir=_resolve_tiered_value(
            field_name="paths.source_dir",
            override_value=override_paths.get("source_dir"),
            settings_value=settings_paths.get("source_dir"),
            parser=_coerce_path,
        ),
        output_dir=_resolve_tiered_value(
            field_name="paths.output_dir",
            override_value=override_paths.get("output_dir"),
            settings_value=settings_paths.get("output_dir"),
            parser=_coerce_path,
        ),
    )


def _resolve_runtime_settings(overrides: Mapping[str, Any] | None, settings: Mapping[str, Any] | None) -> RuntimeSettings:
    override_runtime = _as_mapping(overrides)
    settings_runtime = _as_mapping(settings)
    return RuntimeSettings(
        dry_run=_resolve_tiered_value(
            field_name="runtime.dry_run",
            override_value=override_runtime.get("dry_run"),
            settings_value=settings_runtime.get("dry_run"),
            default_value=False,
            parser=_coerce_bool,
        ),
        overwrite=_resolve_tiered_value(
            field_name="runtime.overwrite",
            override_value=override_runtime.get("overwrite"),
            settings_value=settings_runtime.get("overwrite"),
            default_value=False,
            parser=_coerce_bool,
        ),
        verbose=_resolve_tiered_value(
            field_name="runtime.verbose",
            override_value=override_runtime.get("verbose"),
            settings_value=settings_runtime.get("verbose"),
            default_value=False,
            parser=_coerce_bool,
        ),
    )


def _resolve_image_settings(overrides: Mapping[str, Any] | None, settings: Mapping[str, Any] | None) -> ImageSettings:
    override_image = _as_mapping(overrides.get("image") if isinstance(overrides, Mapping) and "image" in overrides else overrides)
    settings_image = _as_mapping(settings.get("image") if isinstance(settings, Mapping) and "image" in settings else settings)
    return ImageSettings(
        max_longest_edge_px=_resolve_tiered_value(
            field_name="md_gen.image.max_longest_edge_px",
            override_value=override_image.get("max_longest_edge_px"),
            settings_value=settings_image.get("max_longest_edge_px"),
            default_value=1540,
            parser=_coerce_int,
        ),
        token_threshold=_resolve_tiered_value(
            field_name="md_gen.image.token_threshold",
            override_value=override_image.get("token_threshold"),
            settings_value=settings_image.get("token_threshold"),
            default_value=4096,
            parser=_coerce_int,
        ),
    )


def _resolve_prompt_settings(
    *,
    field_name: str,
    override_path: Any,
    settings_path_value: Any,
    default_path: Path,
) -> PromptSettings:
    for candidate, is_default in (
        (override_path, False),
        (settings_path_value, False),
        (default_path, True),
    ):
        resolved_path = _coerce_path(candidate)
        if resolved_path is None:
            continue

        try:
            prompt_text = resolved_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        if not prompt_text.strip():
            continue

        if is_default:
            _warn_default(field_name, resolved_path)
        return PromptSettings(summary_prompt_path=resolved_path, summary_prompt_text=prompt_text)

    return PromptSettings(summary_prompt_path=None, summary_prompt_text=None)


def _resolve_model_settings(
    *,
    section_name: str,
    overrides: Mapping[str, Any] | None,
    settings: Mapping[str, Any] | None,
    default_endpoint: str,
    default_model_name: str,
    default_request_timeout_seconds: float,
    default_request_max_retries: int,
    default_temperature: float,
    default_top_p: float,
    default_top_k: int,
    default_min_p: float,
) -> LlamaModelSettings:
    override_section = _as_mapping(overrides)
    settings_section = _as_mapping(settings)
    return LlamaModelSettings(
        endpoint_url=_resolve_tiered_value(
            field_name=f"{section_name}.endpoint",
            override_value=override_section.get("endpoint"),
            settings_value=settings_section.get("endpoint"),
            default_value=default_endpoint,
            parser=_coerce_text,
        ),
        model_name=_resolve_tiered_value(
            field_name=f"{section_name}.model",
            override_value=override_section.get("model"),
            settings_value=settings_section.get("model"),
            default_value=default_model_name,
            parser=_coerce_text,
        ),
        request_timeout_seconds=_resolve_tiered_value(
            field_name=f"{section_name}.timeout_seconds",
            override_value=override_section.get("timeout_seconds"),
            settings_value=settings_section.get("timeout_seconds"),
            default_value=default_request_timeout_seconds,
            parser=_coerce_float,
        ),
        request_max_retries=_resolve_tiered_value(
            field_name=f"{section_name}.max_retries",
            override_value=override_section.get("max_retries"),
            settings_value=settings_section.get("max_retries"),
            default_value=default_request_max_retries,
            parser=_coerce_int,
        ),
        temperature=_resolve_tiered_value(
            field_name=f"{section_name}.temperature",
            override_value=override_section.get("temperature"),
            settings_value=settings_section.get("temperature"),
            default_value=default_temperature,
            parser=_coerce_float,
        ),
        top_p=_resolve_tiered_value(
            field_name=f"{section_name}.top_p",
            override_value=override_section.get("top_p"),
            settings_value=settings_section.get("top_p"),
            default_value=default_top_p,
            parser=_coerce_float,
        ),
        top_k=_resolve_tiered_value(
            field_name=f"{section_name}.top_k",
            override_value=override_section.get("top_k"),
            settings_value=settings_section.get("top_k"),
            default_value=default_top_k,
            parser=_coerce_int,
        ),
        min_p=_resolve_tiered_value(
            field_name=f"{section_name}.min_p",
            override_value=override_section.get("min_p"),
            settings_value=settings_section.get("min_p"),
            default_value=default_min_p,
            parser=_coerce_float,
        ),
    )


def _resolve_app_config(overrides: Mapping[str, Any] | None, settings_document: Mapping[str, Any] | None) -> AppConfig:
    normalized_settings = _normalize_settings_document(settings_document)
    normalized_overrides = _normalize_settings_document(overrides)

    return AppConfig(
        paths=_resolve_paths_settings(normalized_overrides.get("paths"), normalized_settings.get("paths")),
        ocr_model=_resolve_model_settings(
            section_name="ocr_model",
            overrides=normalized_overrides.get("ocr_model"),
            settings=normalized_settings.get("ocr_model"),
            default_endpoint="http://127.0.0.1:8080/v1/chat/completions",
            default_model_name="lightonocr-2",
            default_request_timeout_seconds=120.0,
            default_request_max_retries=3,
            default_temperature=0.0,
            default_top_p=0.9,
            default_top_k=0,
            default_min_p=0.05,
        ),
        language_model=_resolve_model_settings(
            section_name="language_model",
            overrides=normalized_overrides.get("language_model"),
            settings=normalized_settings.get("language_model"),
            default_endpoint="http://127.0.0.1:8081/v1/chat/completions",
            default_model_name="qwen3-1.7b",
            default_request_timeout_seconds=120.0,
            default_request_max_retries=3,
            default_temperature=0.7,
            default_top_p=0.9,
            default_top_k=0,
            default_min_p=0.05,
        ),
        md_gen=MdGenSettings(
            prompts=_resolve_prompt_settings(
                field_name="md_gen.summary.prompt_path",
                override_path=_nested_get(normalized_overrides.get("md_gen"), "summary", "prompt_path"),
                settings_path_value=_nested_get(normalized_settings.get("md_gen"), "summary", "prompt_path"),
                default_path=DEFAULT_SUMMARY_PROMPT_FILE,
            ),
            image=_resolve_image_settings(normalized_overrides.get("md_gen"), normalized_settings.get("md_gen")),
        ),
        md_mrg=MdMrgSettings(
            score=_resolve_prompt_settings(
                field_name="md_mrg.score.prompt_path",
                override_path=_nested_get(normalized_overrides.get("md_mrg"), "score", "prompt_path"),
                settings_path_value=_nested_get(normalized_settings.get("md_mrg"), "score", "prompt_path"),
                default_path=DEFAULT_SCORE_PROMPT_FILE,
            ),
        ),
        runtime=_resolve_runtime_settings(normalized_overrides.get("runtime"), normalized_settings.get("runtime")),
    )


def _legacy_parse_namespace(args: SimpleNamespace | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(args, Mapping):
        return dict(args)
    return vars(args)


def build_config_from_overrides(overrides: Mapping[str, Any], settings_document: Mapping[str, Any] | None = None) -> AppConfig:
    if settings_document is None:
        settings_document = read_json_settings_file()
    return _resolve_app_config(overrides, settings_document)


def build_config_from_args(args: SimpleNamespace | Mapping[str, Any]) -> AppConfig:
    payload = _legacy_parse_namespace(args)
    overrides = {
        "paths": {
            "source_dir": payload.get("source"),
            "output_dir": payload.get("output"),
        },
        "ocr_model": {
            "endpoint": payload.get("ocr_model_endpoint"),
            "model": payload.get("ocr_model_name"),
            "timeout_seconds": payload.get("ocr_timeout_seconds"),
            "max_retries": payload.get("ocr_max_retries"),
            "temperature": payload.get("ocr_temperature"),
            "top_p": payload.get("ocr_top_p"),
            "top_k": payload.get("ocr_top_k"),
            "min_p": payload.get("ocr_min_p"),
        },
        "language_model": {
            "endpoint": payload.get("language_model_endpoint"),
            "model": payload.get("language_model_name"),
            "timeout_seconds": payload.get("language_timeout_seconds"),
            "max_retries": payload.get("language_max_retries"),
            "temperature": payload.get("temperature"),
            "top_p": payload.get("top_p"),
            "top_k": payload.get("top_k"),
            "min_p": payload.get("min_p"),
        },
        "md_gen": {
            "summary": {"prompt_path": payload.get("summary_prompt")},
            "image": {
                "max_longest_edge_px": payload.get("max_longest_edge_px"),
                "token_threshold": payload.get("token_threshold"),
            },
        },
        "md_mrg": {
            "score": {"prompt_path": payload.get("md_mrg_score_prompt")},
        },
        "runtime": {
            "dry_run": True if payload.get("dry_run") else None,
            "overwrite": True if payload.get("overwrite") else None,
            "verbose": True if payload.get("verbose") else None,
        },
    }
    return build_config_from_overrides(overrides)


def _resolve_optional_file(raw_value: str | None) -> Path | None:
    if not raw_value:
        return None
    return Path(raw_value).expanduser().resolve()


def _resolve_required_directory(raw_value: str) -> Path:
    resolved = Path(raw_value).expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ConfigValidationError(
            "invalid_source_directory",
            f"--source must be an existing directory: {resolved}",
        )
    return resolved


def _resolve_output_directory(raw_value: str) -> Path:
    resolved = Path(raw_value).expanduser().resolve()
    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigValidationError(
            "output_directory_create_failed",
            f"Failed to create --output directory: {resolved}",
        ) from exc
    return resolved


def build_path_settings_from_args(args: SimpleNamespace) -> PathSettings:
    source_dir = Path()
    if hasattr(args, "source") and args.source is not None:
        source_dir = _resolve_required_directory(args.source)

    output_dir = Path()
    if hasattr(args, "output") and args.output is not None:
        output_dir = _resolve_output_directory(args.output)

    return PathSettings(
        source_dir=source_dir,
        output_dir=output_dir,
    )


def build_prompt_settings_from_args(args: SimpleNamespace, json_config: dict) -> PromptSettings:
    summary_prompt_path = _resolve_optional_file(getattr(args, "summary_prompt", None))
    if summary_prompt_path is None:
        summary_prompt_path = _coerce_path(json_config.get("prompt_path"))
    summary_prompt_text = None
    if summary_prompt_path is not None:
        try:
            with open(summary_prompt_path, "r", encoding="utf-8") as file_handle:
                summary_prompt_text = file_handle.read()
        except (OSError, UnicodeDecodeError):
            summary_prompt_text = None

    return PromptSettings(
        summary_prompt_path=summary_prompt_path,
        summary_prompt_text=summary_prompt_text,
    )


def build_llama_model_settings_from_args(args: SimpleNamespace, json_config: dict) -> LlamaModelSettings:
    return _resolve_model_settings(
        section_name="language_model",
        overrides={
            "endpoint": getattr(args, "model_endpoint", None),
            "model": getattr(args, "model_name", None),
            "timeout_seconds": getattr(args, "timeout_seconds", None),
            "max_retries": getattr(args, "max_retries", None),
            "temperature": getattr(args, "temperature", None),
            "top_p": getattr(args, "top_p", None),
            "top_k": getattr(args, "top_k", None),
            "min_p": getattr(args, "min_p", None),
        },
        settings=json_config,
        default_endpoint="http://127.0.0.1:8081/v1/chat/completions",
        default_model_name="qwen3-1.7b",
        default_request_timeout_seconds=120.0,
        default_request_max_retries=3,
        default_temperature=0.7,
        default_top_p=0.9,
        default_top_k=0,
        default_min_p=0.05,
    )


def build_image_settings_from_args(args: SimpleNamespace, json_config: dict) -> ImageSettings:
    return _resolve_image_settings(
        {
            "max_longest_edge_px": getattr(args, "max_longest_edge_px", None),
            "token_threshold": getattr(args, "token_threshold", None),
        },
        json_config,
    )


def build_md_mrg_settings_from_json(json_config: dict) -> MdMrgSettings:
    return MdMrgSettings(
        score=_resolve_prompt_settings(
            field_name="md_mrg.score.prompt_path",
            override_path=None,
            settings_path_value=_nested_get(json_config.get("md_mrg"), "score", "prompt_path"),
            default_path=DEFAULT_SCORE_PROMPT_FILE,
        )
    )


def build_md_mrg_config_from_args(args: SimpleNamespace) -> AppConfig:
    return build_config_from_args(args)
