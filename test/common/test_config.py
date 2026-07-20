from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

import common.config as config


def test_read_json_settings_file_returns_empty_dict_for_missing_or_invalid_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing_settings = tmp_path / "settings.json"
    monkeypatch.setattr(config, "DEFAULT_SETTINGS_FILE", missing_settings)

    assert config.read_json_settings_file() == {}

    missing_settings.write_text("not json", encoding="utf-8")
    assert config.read_json_settings_file() == {}


def test_build_config_from_overrides_uses_sparse_precedence_and_warns_once_for_defaults(tmp_path: Path) -> None:
    override_source = tmp_path / "override-source"
    settings_output = tmp_path / "settings-output"
    override_prompt = tmp_path / "override-summary.md"
    settings_prompt = tmp_path / "settings-summary.md"
    score_prompt = tmp_path / "score.md"
    override_prompt.write_text("override summary", encoding="utf-8")
    settings_prompt.write_text("settings summary", encoding="utf-8")
    score_prompt.write_text("score prompt", encoding="utf-8")

    overrides = {
        "paths": {"source_dir": str(override_source)},
        "language_model": {"model": "override-language"},
        "md_gen": {"summary": {"prompt_path": str(override_prompt)}},
        "runtime": {"overwrite": True},
    }
    settings_document = {
        "paths": {"output_dir": str(settings_output)},
        "ocr_model": {
            "endpoint": "http://settings-ocr",
            "model": "ocr-model",
            "timeout_seconds": 44.0,
            "max_retries": 5,
            "temperature": 0.1,
            "top_p": 0.8,
            "top_k": 1,
            "min_p": 0.01,
        },
        "language_model": {
            "endpoint": "http://settings-language",
            "model": "settings-language",
            "timeout_seconds": 55.0,
            "max_retries": 6,
            "temperature": 0.4,
            "top_p": 0.7,
            "top_k": 2,
            "min_p": 0.02,
        },
        "md_gen": {
            "summary": {"prompt_path": str(settings_prompt)},
            "image": {"max_longest_edge_px": 1800, "token_threshold": 9000},
        },
        "md_mrg": {"score": {"prompt_path": str(score_prompt)}},
        "runtime": {"dry_run": True, "overwrite": False},
    }

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        app_config = config.build_config_from_overrides(overrides, settings_document)

    assert app_config.paths.source_dir == override_source.resolve()
    assert app_config.paths.output_dir == settings_output.resolve()
    assert app_config.ocr_model.endpoint_url == "http://settings-ocr"
    assert app_config.ocr_model.model_name == "ocr-model"
    assert app_config.language_model.endpoint_url == "http://settings-language"
    assert app_config.language_model.model_name == "override-language"
    assert app_config.md_gen.prompts.summary_prompt_path == override_prompt.resolve()
    assert app_config.md_gen.prompts.summary_prompt_text == "override summary"
    assert app_config.md_mrg.score.summary_prompt_path == score_prompt.resolve()
    assert app_config.runtime.dry_run is True
    assert app_config.runtime.overwrite is True
    assert app_config.runtime.verbose is False

    assert [str(warning.message) for warning in captured_warnings] == [
        "Using default for runtime.verbose: False",
    ]


def test_build_config_from_overrides_leaves_unresolved_shared_paths_empty_when_missing(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("prompt text", encoding="utf-8")

    app_config = config.build_config_from_overrides(
        {
            "md_gen": {"summary": {"prompt_path": str(prompt_file)}},
            "md_mrg": {"score": {"prompt_path": str(prompt_file)}},
        },
        {},
    )

    assert app_config.paths.source_dir is None
    assert app_config.paths.output_dir is None


def test_build_md_mrg_settings_from_json_falls_back_to_default_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    default_prompt = tmp_path / "default-score.md"
    default_prompt.write_text("default score prompt", encoding="utf-8")
    monkeypatch.setattr(config, "DEFAULT_SCORE_PROMPT_FILE", default_prompt)

    settings = config.build_md_mrg_settings_from_json({})

    assert settings.score.summary_prompt_path == default_prompt.resolve()
    assert settings.score.summary_prompt_text == "default score prompt"


def test_build_prompt_settings_from_args_returns_none_when_unset() -> None:
    prompt_settings = config.build_prompt_settings_from_args(
        type("Args", (), {"summary_prompt": None})(),
        {},
    )

    assert prompt_settings.summary_prompt_path is None
    assert prompt_settings.summary_prompt_text is None


def test_build_image_settings_from_args_uses_provided_values() -> None:
    image_settings = config.build_image_settings_from_args(
        type("Args", (), {"max_longest_edge_px": 2048, "token_threshold": 4096})(),
        {},
    )

    assert image_settings.max_longest_edge_px == 2048
    assert image_settings.token_threshold == 4096
