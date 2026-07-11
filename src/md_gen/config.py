from __future__ import annotations

import json
import shutil

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace


class ConfigValidationError(ValueError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


DEFAULT_SETTINGS_FILE = Path(__file__).resolve().parents[2] / "data" / "config" / "settings.json"

DEFAULT_SUMMARY_PROMPT_FILE = Path(__file__).resolve().parents[2] / "data" / "prompts" / "md_gen_summary_system_prompt.txt"

BUILTIN_SUMMARY_PROMPT = (
    "You are an automated data-extraction parser. You process OCR text and output a concise summary "
    "no longer than three lines.\n\n"
    "CRITICAL INSTRUCTIONS:\n"
    "- Do not use thinking tags (<think>...</think>).\n"
    "- Do not output chain-of-thought reasoning, explanations, or introductory text.\n"
    "- Return only plain text summary content.\n"
    "- Avoid markdown formatting."
)


@dataclass(frozen=True)
class PathSettings:
    source_dir: Path
    output_dir: Path
    temp_dir: Path


@dataclass(frozen=True)
class PromptSettings:
    summary_prompt_path: Path | None
    summary_prompt_text: str


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


def read_json_settings_file() -> dict:
    if not DEFAULT_SETTINGS_FILE.exists():
        default_settings_path = DEFAULT_SETTINGS_FILE.parent
        default_settings_path.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(default_settings_path / "settings-default.json", DEFAULT_SETTINGS_FILE)
        except OSError as exc:
            raise ConfigValidationError(
                "settings_file_create_failed",
                f"Failed to create default settings.json file at: {DEFAULT_SETTINGS_FILE}",
            ) from exc
        
    # Now read the settings.json file.
    try:
        with open(DEFAULT_SETTINGS_FILE, "r", encoding="utf-8") as f:
            json_config = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigValidationError(
            "settings_file_read_failed",
            f"Failed to read or parse settings.json file at: {DEFAULT_SETTINGS_FILE}",
        ) from exc
    
    return json_config


def build_path_settings_from_args(args: SimpleNamespace) -> PathSettings:
    source_dir = _resolve_required_directory(args.source)
    output_dir = _resolve_output_directory(args.output)
    temp_dir = output_dir / "temp"
    return PathSettings(
        source_dir=source_dir,
        output_dir=output_dir,
        temp_dir=temp_dir,
    )


def build_prompt_settings_from_args(args: SimpleNamespace, json_config: dict) -> PromptSettings:
    summary_prompt_path = _resolve_optional_file(getattr(args, "summary_prompt", None))
    if summary_prompt_path is None:
        summary_prompt_path = json_config.get("prompt_path", None)
    if summary_prompt_path is not None:
        try:
            with open(summary_prompt_path, "r", encoding="utf-8") as f:
                summary_prompt_text = f.read()
        except (OSError, UnicodeDecodeError) as exc:
            raise ConfigValidationError(
                "summary_prompt_read_failed",
                f"Failed to read summary prompt file at: {summary_prompt_path}",
            ) from exc
    else:
        summary_prompt_text = BUILTIN_SUMMARY_PROMPT
    
    return PromptSettings(
        summary_prompt_path=summary_prompt_path,
        summary_prompt_text=summary_prompt_text,
    )

def build_llama_model_settings_from_args(args: SimpleNamespace, json_config: dict) -> LlamaModelSettings:
    _endpoint_url=args.model_endpoint
    if _endpoint_url is None:
        _endpoint_url = json_config.get("endpoint")
    if _endpoint_url is None:
        raise ConfigValidationError(
            "model_endpoint_not_specified",
            "Model endpoint URL must be specified either in the JSON config or as a command-line argument.",
        )
    
    _model_name=args.model_name
    if _model_name is None:
        _model_name = json_config.get("model", None)
    if _model_name is None:
        raise ConfigValidationError(
            "model_name_not_specified",
            "Model name must be specified either in the JSON config or as a command-line argument.",
        )
    
    _request_timeout_seconds=args.timeout_seconds
    if _request_timeout_seconds is None:
        _request_timeout_seconds = json_config.get("timeout_seconds")
    if _request_timeout_seconds is None:
        _request_timeout_seconds = 120.0
        print("INFO: Using default model request timeout of 120.0 seconds (missing setting in JSON and command-line argument)")

    _request_max_retries=args.max_retries
    if _request_max_retries is None:
        _request_max_retries = json_config.get("max_retries")
    if _request_max_retries is None:
        _request_max_retries = 2
        print("INFO: Using default model request max retries of 2 (missing setting in JSON and command-line argument)")

    return LlamaModelSettings(
        endpoint_url = _endpoint_url,
        model_name = _model_name,
        request_timeout_seconds = _request_timeout_seconds,
        request_max_retries = _request_max_retries,
    )

def build_image_settings_from_args(args: SimpleNamespace, json_config: dict) -> ImageSettings:
    _max_longest_edge_px = args.max_longest_edge_px
    if _max_longest_edge_px is None:
        _max_longest_edge_px = json_config.get("max_longest_edge_px")
        if _max_longest_edge_px is None:
            _max_longest_edge_px = 1540
            print("INFO: Using default max longest edge of 1540 pixels (missing setting in JSON and command-line argument)")

    _token_threshold = args.token_threshold
    if _token_threshold is None:
        _token_threshold = json_config.get("token_threshold")
        if _token_threshold is None:
            _token_threshold = 16000
            print("INFO: Using default token threshold of 16000 (missing setting in JSON and command-line argument)")

    return ImageSettings(
        max_longest_edge_px=_max_longest_edge_px,
        token_threshold=_token_threshold,
    )

def build_config_from_args(args: SimpleNamespace) -> AppConfig:
    # First make sure the settings.json file exists and is valid. Is not, we must write a default one.
    json_config = read_json_settings_file()

    _paths = build_path_settings_from_args(args)

    _prompts = build_prompt_settings_from_args(args, json_config.get("summary", {}))

    _ocr_args = SimpleNamespace(
        model_endpoint=args.ocr_model_endpoint,
        model_name=args.ocr_model_name,
        timeout_seconds=args.ocr_timeout_seconds,
        max_retries=args.ocr_max_retries,
    )
    _ocr_model = build_llama_model_settings_from_args(_ocr_args, json_config.get("ocr_model", {}))

    _language_args = SimpleNamespace(
        model_endpoint=args.language_model_endpoint,
        model_name=args.language_model_name,
        timeout_seconds=args.language_timeout_seconds,
        max_retries=args.language_max_retries,
    )
    _language_model = build_llama_model_settings_from_args(_language_args, json_config.get("language_model", {}))

    _image = build_image_settings_from_args(args, json_config.get("image", {}))

    return AppConfig(
        paths = _paths,
        prompts = _prompts,
        ocr_model = _ocr_model,
        language_model = _language_model,
        image = _image,
        runtime=RuntimeSettings(
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        ),
    )
