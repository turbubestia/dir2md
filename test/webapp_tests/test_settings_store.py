"""Tests for the webapp settings store."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from webapp.backend.models import AppSettings
from webapp.backend.settings_store import (
    SettingsBootstrapError,
    SettingsStoreError,
    _bootstrap_settings_file,
    load_settings,
    save_settings,
)


@pytest.fixture
def tmp_settings_paths(tmp_path: Path):
    """Provide isolated settings and defaults files for a test."""
    defaults = tmp_path / "settings-default.json"
    defaults.write_text(
        json.dumps(
            {
                "app_name": "dir2md",
                "version": "0.1.0",
                "source_folder": "",
                "output_folder": "",
                "verbose": False,
                "overwrite": False,
                "ocr_model": {
                    "endpoint": "http://127.0.0.1:8080/v1/chat/completions",
                    "model": "lightonocr-2",
                    "timeout_seconds": 120,
                    "max_retries": 3,
                },
                "language_model": {
                    "endpoint": "http://127.0.0.1:8081/v1/chat/completions",
                    "model": "qwen3-1.7b",
                    "timeout_seconds": 120,
                    "max_retries": 3,
                },
                "md_gen": {
                    "summary": {
                        "prompt_path": "data/prompts/md_gen_summary_system_prompt.md",
                    },
                    "image": {
                        "max_longest_edge_px": 1540,
                        "token_threshold": 4096,
                    },
                },
                "md_mrg": {
                    "score": {
                        "prompt_path": "data/prompts/md_mrg_score_system_prompt.md",
                    },
                },
            },
            indent=4,
        ),
        encoding="utf-8",
    )
    settings = tmp_path / "settings.json"
    return settings, defaults


def test_load_settings_bootstraps_from_defaults(tmp_settings_paths):
    settings_path, defaults_path = tmp_settings_paths
    assert not settings_path.exists()

    loaded = load_settings(settings_path, defaults_path)

    assert isinstance(loaded, AppSettings)
    assert loaded.app_name == "dir2md"
    assert settings_path.exists()


def test_load_settings_returns_existing_values(tmp_settings_paths):
    settings_path, defaults_path = tmp_settings_paths
    custom = json.loads(defaults_path.read_text(encoding="utf-8"))
    custom["source_folder"] = "C:\\source"
    custom["output_folder"] = "C:\\output"
    settings_path.write_text(json.dumps(custom), encoding="utf-8")

    loaded = load_settings(settings_path, defaults_path)

    assert loaded.source_folder == "C:\\source"
    assert loaded.output_folder == "C:\\output"


def test_load_settings_invalid_json_raises(tmp_settings_paths):
    settings_path, defaults_path = tmp_settings_paths
    settings_path.write_text("not json", encoding="utf-8")

    with pytest.raises(SettingsStoreError):
        load_settings(settings_path, defaults_path)


def test_load_settings_schema_violation_raises(tmp_settings_paths):
    settings_path, defaults_path = tmp_settings_paths
    settings_path.write_text(json.dumps({"app_name": "x"}), encoding="utf-8")

    with pytest.raises(SettingsStoreError):
        load_settings(settings_path, defaults_path)


def test_save_settings_round_trips_folder_paths_as_strings(tmp_settings_paths):
    settings_path, defaults_path = tmp_settings_paths
    loaded = load_settings(settings_path, defaults_path)
    loaded.source_folder = "D:\\My Source"
    loaded.output_folder = "D:\\My Output"

    saved = save_settings(loaded, settings_path)

    assert saved.source_folder == "D:\\My Source"
    assert saved.output_folder == "D:\\My Output"
    disk = json.loads(settings_path.read_text(encoding="utf-8"))
    assert disk["source_folder"] == "D:\\My Source"
    assert disk["output_folder"] == "D:\\My Output"


def test_save_settings_is_atomic(tmp_settings_paths):
    settings_path, defaults_path = tmp_settings_paths
    loaded = load_settings(settings_path, defaults_path)
    loaded.source_folder = "atomic-test"

    save_settings(loaded, settings_path)

    # Ensure the target file exists and no temporary sibling leaked.
    assert settings_path.exists()
    siblings = [p for p in settings_path.parent.iterdir() if p.name.startswith(".")]
    assert not siblings


def test_bootstrap_missing_defaults_raises(tmp_path: Path):
    missing_defaults = tmp_path / "missing-defaults.json"
    target = tmp_path / "settings.json"

    with pytest.raises(SettingsBootstrapError):
        _bootstrap_settings_file(target, missing_defaults)


def test_save_settings_persists_valid_json(tmp_settings_paths):
    settings_path, defaults_path = tmp_settings_paths
    loaded = load_settings(settings_path, defaults_path)

    save_settings(loaded, settings_path)

    raw = json.loads(settings_path.read_text(encoding="utf-8"))
    assert raw["app_name"] == "dir2md"
    assert "ocr_model" in raw
    assert "md_gen" in raw
    assert "md_mrg" in raw
