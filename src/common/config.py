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
DEFAULT_SUMMARY_PROMPT_FILE = Path(__file__).resolve().parents[2] / "data" / "prompts" / "md_gen_summary_system_prompt.md"


@dataclass(frozen=True)
class PathSettings:
    source_dir: Path
    output_dir: Path


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
    return PathSettings(
        source_dir=source_dir,
        output_dir=output_dir,
    )


def build_prompt_settings_from_args(args: SimpleNamespace, json_config: dict) -> PromptSettings:
    summary_prompt_path = _resolve_optional_file(getattr(args, "summary_prompt", None))
    if summary_prompt_path is None:
        summary_prompt_path = json_config.get("prompt_path")
    summary_prompt_text = None
    if summary_prompt_path is not None:
        try:
            with open(summary_prompt_path, "r", encoding="utf-8") as f:
                summary_prompt_text = f.read()
        except (OSError, UnicodeDecodeError) as exc:
            raise ConfigValidationError(
                "summary_prompt_read_failed",
                f"Failed to read summary prompt file at: {summary_prompt_path}",
            ) from exc
    
    if summary_prompt_text is None:
        raise ConfigValidationError(
            "summary_prompt_not_specified",
            "Summary prompt path must be specified either in the JSON config or as a command-line argument.",
        ) 
    
    return PromptSettings(
        summary_prompt_path=summary_prompt_path,
        summary_prompt_text=summary_prompt_text,
    )

def build_llama_model_settings_from_args(args: SimpleNamespace, json_config: dict) -> LlamaModelSettings:
    _endpoint_url = getattr(args, "model_endpoint", None)
    if _endpoint_url is None:
        _endpoint_url = json_config.get("endpoint")
    if _endpoint_url is None:
        raise ConfigValidationError(
            "model_endpoint_not_specified",
            "Model endpoint URL must be specified either in the JSON config or as a command-line argument.",
        )
    
    _model_name = getattr(args, "model_name", None)
    if _model_name is None:
        _model_name = json_config.get("model", None)
    if _model_name is None:
        raise ConfigValidationError(
            "model_name_not_specified",
            "Model name must be specified either in the JSON config or as a command-line argument.",
        )
    
    _request_timeout_seconds = getattr(args, "timeout_seconds", None)
    if _request_timeout_seconds is None:
        _request_timeout_seconds = json_config.get("timeout_seconds")
    if _request_timeout_seconds is None:
        _request_timeout_seconds = 120.0
        print("INFO: Using default model request timeout of 120.0 seconds (missing setting in JSON and command-line argument)")

    _request_max_retries = getattr(args, "max_retries", None)
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
    _max_longest_edge_px = getattr(args, "max_longest_edge_px", None)
    if _max_longest_edge_px is None:
        _max_longest_edge_px = json_config.get("max_longest_edge_px")
        if _max_longest_edge_px is None:
            _max_longest_edge_px = 1540
            print("INFO: Using default max longest edge of 1540 pixels (missing setting in JSON and command-line argument)")

    _token_threshold = getattr(args, "token_threshold", None)
    if _token_threshold is None:
        _token_threshold = json_config.get("token_threshold")
        if _token_threshold is None:
            _token_threshold = 16000
            print("INFO: Using default token threshold of 16000 (missing setting in JSON and command-line argument)")

    return ImageSettings(
        max_longest_edge_px=_max_longest_edge_px,
        token_threshold=_token_threshold,
    )


def build_md_mrg_settings_from_json(json_config: dict) -> MdMrgSettings:
    md_mrg_json = json_config.get("md_mrg", {})
    if not md_mrg_json:
        raise ConfigValidationError(
            "md_mrg_config_missing",
            "Missing 'md_mrg' section in settings.json file.",
        )

    score_json = md_mrg_json.get("score", {})
    prompt_path_raw = score_json.get("prompt_path")
    if not prompt_path_raw:
        raise ConfigValidationError(
            "md_mrg_score_prompt_missing",
            "Missing 'md_mrg.score.prompt_path' in settings.json file.",
        )

    prompt_path = Path(prompt_path_raw).expanduser().resolve()
    try:
        score_prompt_text = prompt_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigValidationError(
            "md_mrg_score_prompt_read_failed",
            f"Failed to read md_mrg score prompt file at: {prompt_path}",
        ) from exc

    if not score_prompt_text.strip():
        raise ConfigValidationError(
            "md_mrg_score_prompt_empty",
            f"md_mrg score prompt file is empty: {prompt_path}",
        )

    return MdMrgSettings(score=PromptSettings(
        summary_prompt_path=prompt_path,
        summary_prompt_text=score_prompt_text,
    ))


def build_md_mrg_config_from_args(args: SimpleNamespace) -> AppConfig:
    json_config = read_json_settings_file()

    source_dir = _resolve_required_directory(args.source)

    md_gen_json = json_config.get("md_gen", {})
    if not md_gen_json:
        raise ConfigValidationError(
            "md_gen_config_missing",
            "Missing 'md_gen' section in settings.json file.",
        )

    md_gen_settings = MdGenSettings(
        prompts=build_prompt_settings_from_args(
            SimpleNamespace(summary_prompt=None),
            md_gen_json.get("summary", {}),
        ),
        image=build_image_settings_from_args(SimpleNamespace(), md_gen_json.get("image", {})),
    )

    _language_args = SimpleNamespace(
        model_endpoint=getattr(args, "language_model_endpoint", None),
        model_name=getattr(args, "language_model_name", None),
        timeout_seconds=getattr(args, "language_timeout_seconds", None),
        max_retries=getattr(args, "language_max_retries", None),
    )
    language_model = build_llama_model_settings_from_args(_language_args, json_config.get("language_model", {}))

    md_mrg_settings = build_md_mrg_settings_from_json(json_config)

    return AppConfig(
        paths=PathSettings(source_dir=source_dir, output_dir=source_dir),
        ocr_model=build_llama_model_settings_from_args(SimpleNamespace(), json_config.get("ocr_model", {})),
        language_model=language_model,
        md_gen=md_gen_settings,
        md_mrg=md_mrg_settings,
        runtime=RuntimeSettings(
            dry_run=False,
            overwrite=getattr(args, "overwrite", False),
        ),
    )

def build_config_from_args(args: SimpleNamespace) -> AppConfig:
    """Build a fully resolved :class:`AppConfig` from CLI arguments and JSON settings.

    **Design patterns used:**

    1. **Priority Resolution (CLI > JSON > Defaults)**
       Each setting is resolved with a three-tier fallback:
       - CLI arguments (highest priority) — e.g. ``args.ocr_model_endpoint``
       - JSON config file (``settings.json``) — e.g. ``json_config["ocr_model"]["endpoint"]``
       - Hardcoded defaults — e.g. ``120.0`` seconds for timeout
       This is implemented via chained ``getattr`` / ``dict.get`` / inline defaults
       in each ``build_*_from_args`` helper.

    2. **Compositional Construction**
       The top-level :class:`AppConfig` is assembled from smaller, independently
       validated dataclass fragments:
       - :class:`PathSettings` — source/output directories
       - :class:`PromptSettings` — prompt file path and loaded text
       - :class:`LlamaModelSettings` — OCR and language model endpoints
       - :class:`ImageSettings` — image resizing and token thresholds
       - :class:`MdGenSettings` / :class:`MdMrgSettings` — module-specific configs
       - :class:`RuntimeSettings` — dry-run and overwrite flags
       Each fragment is built by a dedicated helper, keeping concerns separated
       and testable in isolation.

    3. **Fail-Fast Validation**
       Every required configuration source is validated at build time. Missing or
       invalid values raise :class:`ConfigValidationError` with a machine-readable
       ``error_code`` (e.g. ``"md_gen_config_missing"``) and a human-readable message.
       The function never returns a partially constructed config.

    4. **Argument Namespacing via ``SimpleNamespace``**
       CLI argument attributes are mapped to a uniform ``model_endpoint`` / ``model_name``
       schema expected by shared helpers (e.g. :func:`build_llama_model_settings_from_args`)
       by wrapping them in :class:`~types.SimpleNamespace`. This avoids duplicating the
       priority-resolution logic for each model type (OCR vs language).

    5. **Immutable Result**
       The returned :class:`AppConfig` is composed entirely of :class:`frozen <dataclass>`
       dataclasses, producing an immutable configuration object that is safe to share
       across modules without defensive copying.

    Args:
        args: A :class:`~types.SimpleNamespace` containing parsed CLI arguments
            (``source``, ``output``, ``ocr_model_endpoint``, ``ocr_model_name``,
            ``ocr_timeout_seconds``, ``ocr_max_retries``, ``language_model_endpoint``,
            ``language_model_name``, ``language_timeout_seconds``, ``language_max_retries``,
            ``max_longest_edge_px``, ``token_threshold``, ``dry_run``, ``overwrite``,
            ``summary_prompt``).

    Returns:
        A fully resolved :class:`AppConfig` ready for use by ``md_gen`` and ``md_mrg``.

    Raises:
        ConfigValidationError: If any required configuration is missing or invalid.
    """
    # First make sure the settings.json file exists and is valid. Is not, we must write a default one.
    json_config = read_json_settings_file()

    _paths = build_path_settings_from_args(args)

    md_gen_json = json_config.get("md_gen", {})
    if not md_gen_json:
        raise ConfigValidationError(
            "md_gen_config_missing",
            "Missing 'md_gen' section in settings.json file.",
        )

    _prompts = build_prompt_settings_from_args(args, md_gen_json.get("summary", {}))

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

    _image = build_image_settings_from_args(args, md_gen_json.get("image", {}))

    md_mrg_settings = build_md_mrg_settings_from_json(json_config)

    return AppConfig(
        paths=_paths,
        ocr_model=_ocr_model,
        language_model=_language_model,
        md_gen=MdGenSettings(prompts=_prompts, image=_image),
        md_mrg=md_mrg_settings,
        runtime=RuntimeSettings(
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        ),
    )
