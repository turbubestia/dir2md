import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

import common.config as config


def make_args(source: Path, output: Path, **overrides: object) -> SimpleNamespace:
	values = {
		"source": str(source),
		"output": str(output),
		"ocr_model_endpoint": None,
		"ocr_model_name": None,
		"ocr_timeout_seconds": None,
		"ocr_max_retries": None,
		"language_model_endpoint": None,
		"language_model_name": None,
		"language_timeout_seconds": None,
		"language_max_retries": None,
		"summary_prompt": None,
		"max_longest_edge_px": None,
		"token_threshold": None,
		"dry_run": False,
		"overwrite": False,
	}
	values.update(overrides)
	return SimpleNamespace(**values)


def test_config_validation_error_stores_error_code() -> None:
	error = config.ConfigValidationError("test_code", "test message")

	assert error.error_code == "test_code"
	assert str(error) == "test message"


def test_resolve_required_directory_accepts_existing_directory(tmp_path: Path) -> None:
	source_dir = tmp_path / "source"
	source_dir.mkdir()

	assert config._resolve_required_directory(str(source_dir)) == source_dir.resolve()


@pytest.mark.parametrize(
	("path_factory", "expected_code"),
	[
		("missing", "invalid_source_directory"),
		("file", "invalid_source_directory"),
	],
)
def test_resolve_required_directory_rejects_invalid_paths(
	tmp_path: Path,
	path_factory: str,
	expected_code: str,
) -> None:
	if path_factory == "missing":
		invalid_path = tmp_path / "missing-source"
	else:
		invalid_path = tmp_path / "source.txt"
		invalid_path.write_text("not a directory", encoding="utf-8")

	with pytest.raises(config.ConfigValidationError) as exc_info:
		config._resolve_required_directory(str(invalid_path))

	assert exc_info.value.error_code == expected_code


def test_resolve_output_directory_creates_directory(tmp_path: Path) -> None:
	output_dir = tmp_path / "output"

	assert config._resolve_output_directory(str(output_dir)) == output_dir.resolve()
	assert output_dir.is_dir()


def test_resolve_output_directory_returns_existing_directory(tmp_path: Path) -> None:
	output_dir = tmp_path / "existing-output"
	output_dir.mkdir()

	assert config._resolve_output_directory(str(output_dir)) == output_dir.resolve()


def test_resolve_output_directory_raises_when_creation_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	def raise_oserror(self: Path, parents: bool = False, exist_ok: bool = False) -> None:
		raise OSError("cannot create directory")

	monkeypatch.setattr(Path, "mkdir", raise_oserror)

	with pytest.raises(config.ConfigValidationError) as exc_info:
		config._resolve_output_directory(str(tmp_path / "output"))

	assert exc_info.value.error_code == "output_directory_create_failed"


def test_resolve_optional_file_handles_none_empty_and_real_path(tmp_path: Path) -> None:
	prompt_file = tmp_path / "prompt.txt"
	prompt_file.write_text("prompt text", encoding="utf-8")

	assert config._resolve_optional_file(None) is None
	assert config._resolve_optional_file("") is None
	assert config._resolve_optional_file(str(prompt_file)) == prompt_file.resolve()


def test_read_json_settings_file_reads_existing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	settings_file = tmp_path / "settings.json"
	settings_file.write_text(json.dumps({"value": 42}), encoding="utf-8")
	monkeypatch.setattr(config, "DEFAULT_SETTINGS_FILE", settings_file)

	assert config.read_json_settings_file() == {"value": 42}


def test_read_json_settings_file_bootstraps_from_default_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	settings_file = tmp_path / "settings.json"
	default_settings_file = tmp_path / "settings-default.json"
	default_settings_file.write_text(json.dumps({"bootstrapped": True}), encoding="utf-8")
	monkeypatch.setattr(config, "DEFAULT_SETTINGS_FILE", settings_file)

	result = config.read_json_settings_file()

	assert settings_file.exists()
	assert result == {"bootstrapped": True}


def test_read_json_settings_file_raises_when_bootstrap_copy_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	settings_file = tmp_path / "nested" / "settings.json"
	monkeypatch.setattr(config, "DEFAULT_SETTINGS_FILE", settings_file)

	with pytest.raises(config.ConfigValidationError) as exc_info:
		config.read_json_settings_file()

	assert exc_info.value.error_code == "settings_file_create_failed"


def test_read_json_settings_file_raises_for_invalid_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	settings_file = tmp_path / "settings.json"
	settings_file.write_text("{invalid json", encoding="utf-8")
	monkeypatch.setattr(config, "DEFAULT_SETTINGS_FILE", settings_file)

	with pytest.raises(config.ConfigValidationError) as exc_info:
		config.read_json_settings_file()

	assert exc_info.value.error_code == "settings_file_read_failed"


def test_build_path_settings_from_args(tmp_path: Path) -> None:
	source_dir = tmp_path / "source"
	source_dir.mkdir()
	output_dir = tmp_path / "output"
	args = make_args(source_dir, output_dir)

	path_settings = config.build_path_settings_from_args(args)

	assert path_settings.source_dir == source_dir.resolve()
	assert path_settings.output_dir == output_dir.resolve()


@pytest.mark.parametrize(
	("args_summary_prompt", "json_summary", "expected_text"),
	[
		("args", {}, "args prompt"),
		(None, {"prompt_path": "json"}, "json prompt")
	],
)
def test_build_prompt_settings_from_args_uses_expected_prompt_source(
	tmp_path: Path,
	args_summary_prompt: str | None,
	json_summary: dict,
	expected_text: str,
) -> None:
	prompt_file = tmp_path / "prompt.txt"
	prompt_file.write_text(f"{expected_text}", encoding="utf-8")

	if args_summary_prompt == "args":
		args = SimpleNamespace(summary_prompt=str(prompt_file))
		json_config = {}
		expected_path = prompt_file.resolve()
	elif json_summary:
		args = SimpleNamespace(summary_prompt=None)
		json_config = {"prompt_path": str(prompt_file)}
		expected_path = str(prompt_file.resolve())
	else:
		args = SimpleNamespace(summary_prompt=None)
		json_config = {}
		expected_path = None

	prompt_settings = config.build_prompt_settings_from_args(args, json_config)

	assert prompt_settings.summary_prompt_path == expected_path
	assert prompt_settings.summary_prompt_text == expected_text


def test_build_prompt_settings_from_args_raises_for_unreadable_file(tmp_path: Path) -> None:
	prompt_file = tmp_path / "missing-prompt.txt"
	args = SimpleNamespace(summary_prompt=str(prompt_file))

	with pytest.raises(config.ConfigValidationError) as exc_info:
		config.build_prompt_settings_from_args(args, {})

	assert exc_info.value.error_code == "summary_prompt_read_failed"


def test_build_llama_model_settings_from_args_uses_namespace_values() -> None:
	args = SimpleNamespace(
		model_endpoint="http://namespace-endpoint",
		model_name="namespace-model",
		timeout_seconds=12.5,
		max_retries=7,
	)

	model_settings = config.build_llama_model_settings_from_args(args, {})

	assert model_settings.endpoint_url == "http://namespace-endpoint"
	assert model_settings.model_name == "namespace-model"
	assert model_settings.request_timeout_seconds == 12.5
	assert model_settings.request_max_retries == 7


def test_build_llama_model_settings_from_args_uses_json_values() -> None:
	args = SimpleNamespace(
		model_endpoint=None,
		model_name=None,
		timeout_seconds=None,
		max_retries=None,
	)
	json_config = {
		"endpoint": "http://json-endpoint",
		"model": "json-model",
		"timeout_seconds": 55.0,
		"max_retries": 3,
	}

	model_settings = config.build_llama_model_settings_from_args(args, json_config)

	assert model_settings.endpoint_url == "http://json-endpoint"
	assert model_settings.model_name == "json-model"
	assert model_settings.request_timeout_seconds == 55.0
	assert model_settings.request_max_retries == 3


def test_build_llama_model_settings_from_args_uses_defaults_and_reports_them(capsys: pytest.CaptureFixture[str]) -> None:
	args = SimpleNamespace(
		model_endpoint="http://default-endpoint",
		model_name="default-model",
		timeout_seconds=None,
		max_retries=None,
	)

	model_settings = config.build_llama_model_settings_from_args(args, {})
	captured = capsys.readouterr()

	assert model_settings.request_timeout_seconds == 120.0
	assert model_settings.request_max_retries == 2
	assert "Using default model request timeout" in captured.out
	assert "Using default model request max retries" in captured.out


@pytest.mark.parametrize(
	("json_config", "expected_code"),
	[
		({"model": "json-model"}, "model_endpoint_not_specified"),
		({"endpoint": "http://json-endpoint"}, "model_name_not_specified"),
	],
)
def test_build_llama_model_settings_from_args_requires_endpoint_and_model(
	json_config: dict,
	expected_code: str,
) -> None:
	args = SimpleNamespace(
		model_endpoint=None,
		model_name=None,
		timeout_seconds=None,
		max_retries=None,
	)

	with pytest.raises(config.ConfigValidationError) as exc_info:
		config.build_llama_model_settings_from_args(args, json_config)

	assert exc_info.value.error_code == expected_code


def test_build_image_settings_from_args_uses_namespace_values() -> None:
	args = SimpleNamespace(max_longest_edge_px=2048, token_threshold=4096)

	image_settings = config.build_image_settings_from_args(args, {})

	assert image_settings.max_longest_edge_px == 2048
	assert image_settings.token_threshold == 4096


def test_build_image_settings_from_args_uses_json_values() -> None:
	args = SimpleNamespace(max_longest_edge_px=None, token_threshold=None)

	image_settings = config.build_image_settings_from_args(
		args,
		{"max_longest_edge_px": 1536, "token_threshold": 8192},
	)

	assert image_settings.max_longest_edge_px == 1536
	assert image_settings.token_threshold == 8192


def test_build_image_settings_from_args_uses_defaults_and_reports_them(capsys: pytest.CaptureFixture[str]) -> None:
	args = SimpleNamespace(max_longest_edge_px=None, token_threshold=None)

	image_settings = config.build_image_settings_from_args(args, {})
	captured = capsys.readouterr()

	assert image_settings.max_longest_edge_px == 1540
	assert image_settings.token_threshold == 16000
	assert "Using default max longest edge" in captured.out
	assert "Using default token threshold" in captured.out


def test_build_config_from_args_assembles_full_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	source_dir = tmp_path / "source"
	source_dir.mkdir()
	output_dir = tmp_path / "output"
	prompt_file = tmp_path / "summary-prompt.txt"
	prompt_file.write_text("summary prompt text", encoding="utf-8")
	score_prompt_file = tmp_path / "score-prompt.txt"
	score_prompt_file.write_text("score prompt text", encoding="utf-8")

	monkeypatch.setattr(
		config,
		"read_json_settings_file",
		lambda: {
			"ocr_model": {
				"endpoint": "http://ocr-endpoint", 
				"model": "ocr-model"
			},
			"language_model": {
				"endpoint": "http://language-endpoint",
				"model": "language-model",
				"timeout_seconds": 44.0,
				"max_retries": 5,
			},
			"md_gen": {
				"summary": {"prompt_path": str(prompt_file)},
				"image": {"max_longest_edge_px": 900, "token_threshold": 7777},
			},
			"md_mrg": {"score": {"prompt_path": str(score_prompt_file)}},
		},
	)
	args = make_args(source_dir, output_dir, dry_run=True, overwrite=True)

	app_config = config.build_config_from_args(args)

	assert app_config.paths.source_dir == source_dir.resolve()
	assert app_config.paths.output_dir == output_dir.resolve()
	assert app_config.md_gen.prompts.summary_prompt_path == str(prompt_file.resolve())
	assert app_config.md_gen.prompts.summary_prompt_text == "summary prompt text"
	assert app_config.ocr_model.endpoint_url == "http://ocr-endpoint"
	assert app_config.ocr_model.model_name == "ocr-model"
	assert app_config.ocr_model.request_timeout_seconds == 120.0
	assert app_config.ocr_model.request_max_retries == 2
	assert app_config.language_model.endpoint_url == "http://language-endpoint"
	assert app_config.language_model.model_name == "language-model"
	assert app_config.language_model.request_timeout_seconds == 44.0
	assert app_config.language_model.request_max_retries == 5
	assert app_config.md_gen.image.max_longest_edge_px == 900
	assert app_config.md_gen.image.token_threshold == 7777
	assert app_config.runtime.dry_run is True
	assert app_config.runtime.overwrite is True


def test_build_config_from_args_rejects_invalid_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	source_file = tmp_path / "source.txt"
	source_file.write_text("not a directory", encoding="utf-8")
	output_dir = tmp_path / "output"
	monkeypatch.setattr(config, "read_json_settings_file", lambda: {})
	args = make_args(source_file, output_dir)

	with pytest.raises(config.ConfigValidationError) as exc_info:
		config.build_config_from_args(args)

	assert exc_info.value.error_code == "invalid_source_directory"


def test_build_md_mrg_settings_from_json_reads_prompt(tmp_path: Path) -> None:
	prompt_file = tmp_path / "score-prompt.txt"
	prompt_file.write_text("score prompt", encoding="utf-8")

	settings = config.build_md_mrg_settings_from_json(
		{
			"md_mrg": {
				"score": {
					"prompt_path": str(prompt_file),
				}
			}
		}
	)

	assert settings.score.summary_prompt_path == prompt_file.resolve()
	assert settings.score.summary_prompt_text == "score prompt"


@pytest.mark.parametrize(
	("json_payload", "expected_code"),
	[
		({}, "md_mrg_config_missing"),
		({"md_mrg": {}}, "md_mrg_config_missing"),
		({"md_mrg": {"score": {}}}, "md_mrg_score_prompt_missing"),
	],
)
def test_build_md_mrg_settings_from_json_validates_required_keys(json_payload: dict, expected_code: str) -> None:
	with pytest.raises(config.ConfigValidationError) as exc_info:
		config.build_md_mrg_settings_from_json(json_payload)

	assert exc_info.value.error_code == expected_code


def test_build_md_mrg_settings_from_json_rejects_empty_prompt(tmp_path: Path) -> None:
	prompt_file = tmp_path / "empty-prompt.txt"
	prompt_file.write_text("   ", encoding="utf-8")

	with pytest.raises(config.ConfigValidationError) as exc_info:
		config.build_md_mrg_settings_from_json(
			{
				"md_mrg": {
					"score": {
						"prompt_path": str(prompt_file),
					}
				}
			}
		)

	assert exc_info.value.error_code == "md_mrg_score_prompt_empty"


def test_build_md_mrg_config_from_args_assembles_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	source_dir = tmp_path / "source"
	source_dir.mkdir()
	prompt_file = tmp_path / "score-prompt.txt"
	prompt_file.write_text("score prompt", encoding="utf-8")
	summary_prompt_file = tmp_path / "summary-prompt.txt"
	summary_prompt_file.write_text("summary prompt", encoding="utf-8")

	monkeypatch.setattr(
		config,
		"read_json_settings_file",
		lambda: {
			"ocr_model": {
				"endpoint": "http://ocr-endpoint",
				"model": "ocr-model",
			},
			"language_model": {
				"endpoint": "http://language-endpoint",
				"model": "language-model",
				"timeout_seconds": 44.0,
				"max_retries": 5,
			},
			"md_gen": {
				"summary": {"prompt_path": str(summary_prompt_file)},
				"image": {"max_longest_edge_px": 1540, "token_threshold": 4096},
			},
			"md_mrg": {
				"score": {
					"prompt_path": str(prompt_file),
				}
			},
		},
	)

	args = Namespace(
		source=str(source_dir),
		language_model_endpoint=None,
		language_model_name=None,
		language_timeout_seconds=None,
		language_max_retries=None,
	)

	md_mrg_config = config.build_md_mrg_config_from_args(args)

	assert md_mrg_config.paths.source_dir == source_dir.resolve()
	assert md_mrg_config.language_model.endpoint_url == "http://language-endpoint"
	assert md_mrg_config.language_model.model_name == "language-model"
	assert md_mrg_config.language_model.request_timeout_seconds == 44.0
	assert md_mrg_config.language_model.request_max_retries == 5
	assert md_mrg_config.md_mrg.score.summary_prompt_path == prompt_file.resolve()
	assert md_mrg_config.md_mrg.score.summary_prompt_text == "score prompt"

