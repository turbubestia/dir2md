from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace


class ConfigValidationError(ValueError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


DEFAULT_SUMMARY_PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts" / "md_gen_summary_system_prompt.txt"
BUILTIN_SUMMARY_PROMPT = (
    "You are an automated data-extraction parser. You process OCR text and output a concise summary "
    "no longer than three lines.\n\n"
    "CRITICAL INSTRUCTIONS:\n"
    "- DO NOT use thinking tags (<think>...</think>).\n"
    "- DO NOT output chain-of-thought reasoning, explanations, or introductory text.\n"
    "- Return only plain text summary content.\n"
    "- Avoid markdown formatting."
)


@dataclass(frozen=True)
class PathSettings:
    source_dir: Path
    output_dir: Path
    temp_dir: Path
    im_temp_dir: Path
    md_temp_dir: Path
    metadata_temp_dir: Path


@dataclass(frozen=True)
class PromptSettings:
    summary_prompt_override_path: Path | None
    summary_prompt_default_path: Path
    summary_prompt_builtin_text: str

@dataclass(frozen=True)
class LlamaModelSettings:
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
    prompts: PromptSettings
    ocr_model: LlamaModelSettings
    language_model: LlamaModelSettings
    image: ImageSettings
    runtime: RuntimeSettings


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


def _resolve_optional_file(raw_value: str | None) -> Path | None:
    if not raw_value:
        return None
    return Path(raw_value).expanduser().resolve()


def build_config_from_args(args: SimpleNamespace) -> AppConfig:
    source_dir = _resolve_required_directory(args.source)
    output_dir = _resolve_output_directory(args.output)
    temp_dir = output_dir / "temp"
    summary_prompt_override_path = _resolve_optional_file(getattr(args, "summary_prompt", None))

    return AppConfig(
        paths=PathSettings(
            source_dir=source_dir,
            output_dir=output_dir,
            temp_dir=temp_dir,
            im_temp_dir=temp_dir / "images",
            md_temp_dir=temp_dir / "markdown",
            metadata_temp_dir=temp_dir / "metadata",
        ),
        prompts=PromptSettings(
            summary_prompt_override_path=summary_prompt_override_path,
            summary_prompt_default_path=DEFAULT_SUMMARY_PROMPT_FILE,
            summary_prompt_builtin_text=BUILTIN_SUMMARY_PROMPT,
        ),
        ocr_model=LlamaModelSettings(
            endpoint_url=args.ocr_model_endpoint_url,
            model_name=args.ocr_model_name,
            request_timeout_seconds=args.ocr_request_timeout_seconds,
            request_max_retries=args.ocr_request_max_retries,
        ),
        language_model=LlamaModelSettings(
            endpoint_url=args.language_model_endpoint_url,
            model_name=args.language_model_name,
            request_timeout_seconds=args.language_request_timeout_seconds,
            request_max_retries=args.language_request_max_retries,
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
