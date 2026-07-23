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
        "md_gen": {"summary": {"system_prompt": str(override_prompt)}},
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
            "summary": {"system_prompt": str(settings_prompt), "assistant_prompt": ""},
            "image": {"max_longest_edge_px": 1800, "token_threshold": 9000},
        },
        "md_mrg": {
            "merge_score": {"system_prompt": str(score_prompt), "assistant_prompt": ""},
            "merge_summary": {"system_prompt": str(score_prompt), "assistant_prompt": ""},
        },
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
    assert app_config.md_gen.prompts.system_path == str(override_prompt.resolve())
    assert app_config.md_gen.prompts.system_text == "override summary"
    assert app_config.md_gen.prompts.assistant_path == ""
    assert app_config.md_gen.prompts.assistant_text == ""
    assert app_config.md_mrg.score.system_path == str(score_prompt.resolve())
    assert app_config.md_mrg.score.system_text == "score prompt"
    assert app_config.md_mrg.score.assistant_path == ""
    assert app_config.md_mrg.score.assistant_text == ""
    assert app_config.md_mrg.summary.system_path == str(score_prompt.resolve())
    assert app_config.md_mrg.summary.system_text == "score prompt"
    assert app_config.md_mrg.summary.assistant_path == ""
    assert app_config.md_mrg.summary.assistant_text == ""
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
            "md_gen": {"summary": {"system_prompt": str(prompt_file)}},
            "md_mrg": {
                "merge_score": {"system_prompt": str(prompt_file)},
                "merge_summary": {"system_prompt": str(prompt_file)},
            },
        },
        {},
    )

    assert app_config.paths.source_dir is None
    assert app_config.paths.output_dir is None


def test_build_config_from_overrides_falls_back_to_default_score_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    default_prompt = tmp_path / "default-score.md"
    default_prompt.write_text("default score prompt", encoding="utf-8")
    monkeypatch.setattr(config, "DEFAULT_SCORE_PROMPT_FILE", default_prompt)

    app_config = config.build_config_from_overrides({}, {})

    assert app_config.md_mrg.score.system_path == str(default_prompt.resolve())
    assert app_config.md_mrg.score.system_text == "default score prompt"
