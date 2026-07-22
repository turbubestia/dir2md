"""File-backed persistence for the webapp settings API.

The store is the only component that reads from and writes to
``data/config/settings.json``. It validates documents through the webapp
Pydantic schema and performs atomic writes so a crash cannot leave the
settings file partially truncated.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from tempfile import mkstemp
from typing import TYPE_CHECKING, Any

from common.config import AppConfig, build_config_from_overrides
from .models import AppSettings

if TYPE_CHECKING:
    pass


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SETTINGS_FILE = PROJECT_ROOT / "data" / "config" / "settings.json"
DEFAULT_SETTINGS_FILE = PROJECT_ROOT / "data" / "config" / "settings-default.json"


class SettingsStoreError(Exception):
    """Raised when settings cannot be read, parsed, validated, or written."""


class SettingsBootstrapError(SettingsStoreError):
    """Raised when the settings file cannot be bootstrapped from defaults."""


def load_settings(
    settings_path: Path = SETTINGS_FILE,
    defaults_path: Path = DEFAULT_SETTINGS_FILE,
) -> AppSettings:
    """Load and validate settings from ``settings_path``.

    If ``settings_path`` does not exist, it is created by copying
    ``defaults_path``. The loaded JSON is validated against
    :class:`AppSettings` and returned.
    """
    if not settings_path.exists():
        _bootstrap_settings_file(settings_path, defaults_path)

    try:
        with settings_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise SettingsStoreError(
            f"Failed to read or parse settings file at {settings_path}: {exc}"
        ) from exc

    try:
        return AppSettings.model_validate(raw)
    except Exception as exc:
        raise SettingsStoreError(
            f"Settings file at {settings_path} does not match the expected schema: {exc}"
        ) from exc


def save_settings(
    payload: AppSettings,
    settings_path: Path = SETTINGS_FILE,
) -> AppSettings:
    """Serialize ``payload`` to JSON and write it atomically to ``settings_path``.

    The write sequence is:

    1. Serialize the validated payload to a compact JSON string.
    2. Create a temporary file in the same directory as ``settings_path``.
    3. Write, flush, and fsync the temporary file.
    4. Replace ``settings_path`` with the temporary file via ``os.replace``.

    Returns the saved payload so the API can echo the persisted document.
    """
    settings_path = settings_path.resolve()
    data = json.dumps(payload.model_dump(mode="json"), indent=4) + "\n"

    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path_str = mkstemp(
            dir=settings_path.parent,
            prefix=f".{settings_path.name}.",
            suffix=".tmp",
        )
        temp_path = Path(temp_path_str)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, settings_path)
            # Best-effort directory sync. On some platforms (notably Windows)
            # fsync on a directory descriptor requires permissions that may not
            # be available in temporary test directories, so failures are ignored.
            try:
                dir_fd = os.open(settings_path.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
        except Exception:
            # Best-effort cleanup of the temporary file on failure.
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
    except Exception as exc:
        raise SettingsStoreError(
            f"Failed to write settings atomically to {settings_path}: {exc}"
        ) from exc

    return payload


def app_settings_to_shared_overrides(payload: AppSettings) -> dict[str, Any]:
    return {
        "paths": {
            "source_dir": payload.source_folder or None,
            "output_dir": payload.output_folder or None,
        },
        "ocr_model": {
            "endpoint": str(payload.ocr_model.endpoint),
            "model": payload.ocr_model.model,
            "timeout_seconds": payload.ocr_model.timeout_seconds,
            "max_retries": payload.ocr_model.max_retries,
        },
        "language_model": {
            "endpoint": str(payload.language_model.endpoint),
            "model": payload.language_model.model,
            "timeout_seconds": payload.language_model.timeout_seconds,
            "max_retries": payload.language_model.max_retries,
        },
        "md_gen": {
            "summary": {
                "system_prompt": payload.md_gen.summary.system_prompt or None,
                "assistant_prompt": payload.md_gen.summary.assistant_prompt or None,
            },
            "image": {
                "max_longest_edge_px": payload.md_gen.image.max_longest_edge_px,
                "token_threshold": payload.md_gen.image.token_threshold,
            },
        },
        "md_mrg": {
            "merge_score": {
                "system_prompt": payload.md_mrg.score.system_prompt or None,
                "assistant_prompt": payload.md_mrg.score.assistant_prompt or None,
            },
            "merge_summary": {
                "system_prompt": payload.md_mrg.summary.system_prompt or None,
                "assistant_prompt": payload.md_mrg.summary.assistant_prompt or None,
            },
        },
        "runtime": {
            "verbose": payload.verbose or None,
            "overwrite": payload.overwrite or None,
        },
    }


def resolve_shared_config(payload: AppSettings) -> AppConfig:
    return build_config_from_overrides(app_settings_to_shared_overrides(payload), {})


def _bootstrap_settings_file(
    settings_path: Path,
    defaults_path: Path,
) -> None:
    """Create ``settings_path`` by copying ``defaults_path`` if possible."""
    if not defaults_path.exists():
        raise SettingsBootstrapError(
            f"Cannot bootstrap settings: defaults file missing at {defaults_path}"
        )

    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(defaults_path, settings_path)
    except OSError as exc:
        raise SettingsBootstrapError(
            f"Failed to bootstrap settings file at {settings_path} from {defaults_path}: {exc}"
        ) from exc
