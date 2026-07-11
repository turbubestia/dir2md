# Issue 7 - Implementation Plan (md_gen Config Test Coverage)

Analysis file: `issues/7-add-unit-test-md-gen-config.plan.analysis.md`

## 1. Phase Goal

Deliver a real unit test suite for `src/md_gen/config.py` that covers every function in the module and reaches at least 80% module coverage, while staying fully detached from CLI parsing and application startup.

## 2. Scope of This Phase

In scope:
- Replace the current stub in `test/md_gen/test_config.py` with real tests.
- Cover all public and private helper functions in `src/md_gen/config.py`.
- Add success and failure-path tests for filesystem helpers, prompt loading, model settings, image settings, and full config assembly.
- Fix pytest discovery so the repository’s `test/` layout is actually discovered.
- Adjust coverage settings so the config module target is enforceable at 80%.

Out of scope:
- Any behavior changes in `src/md_gen/cli.py`.
- Any md_mrg work.
- Broader refactors in md_gen unrelated to config coverage.

## 3. Preconditions and Dependencies

- The test suite must remain direct and not route through CLI parsing.
- `tmp_path`, `monkeypatch`, and `capsys` are expected to be sufficient for isolating filesystem and default-path behavior.
- If a branch in `src/md_gen/config.py` cannot be isolated cleanly, only then consider a minimal production-code seam in that file.

## 4. Design Decisions Locked for This Phase

- Test target is `src/md_gen/config.py` specifically.
- Minimum coverage target is 80% for that module.
- Tests should cover both happy paths and fallback/error branches.
- The test file remains under `test/md_gen/`.
- The tests must not import or invoke `src/md_gen/cli.py`.

## 5. Implementation Workstreams

## 5.1 Repair pytest Discovery and Coverage Targeting

Target file:
- `pyproject.toml`

Required changes:
- Change pytest `testpaths` from `tests` to `test` so the repository’s actual test tree is discovered.
- Replace or refine the current coverage configuration so it measures the config module rather than only the whole `src` tree.
- Add a coverage threshold that makes the 80% config-module target enforceable.

Planned outcome:
- Running pytest in the project environment discovers the md_gen tests in `test/md_gen`.
- Coverage reporting reflects the module being worked on, not just repository-wide aggregate coverage.

Suggested implementation shape:

```text
pytest discovery:
  testpaths = ["test"]

coverage target:
  --cov=src/md_gen/config.py or equivalent module-scoped coverage selection
  minimum threshold >= 80
```

## 5.2 Replace the Stub in `test/md_gen/test_config.py`

Target file:
- `test/md_gen/test_config.py`

Required changes:
- Replace the current import-only stub with a full test module.
- Import `src.md_gen.config` symbols directly from the module under test.
- Use `argparse.Namespace` or a small equivalent object to simulate CLI-like inputs for helper functions.
- Organize tests around one helper or behavior cluster per test function.

Test structure to include:
- A test for `ConfigValidationError` behavior and stored `error_code`.
- A test group for `_resolve_required_directory`.
- A test group for `_resolve_output_directory`.
- A test group for `_resolve_optional_file`.
- A test group for `read_json_settings_file`.
- A test group for `build_path_settings_from_args`.
- A test group for `build_prompt_settings_from_args`.
- A test group for `build_llama_model_settings_from_args`.
- A test group for `build_image_settings_from_args`.
- At least one integration-style test for `build_config_from_args`.

Suggested test scaffolding:

```text
for each helper:
  arrange temporary filesystem state
  monkeypatch module constants if the helper reads module-level defaults
  build minimal Namespace inputs
  call the helper directly
  assert dataclass fields and error codes/messages
```

## 5.3 Cover Path Resolution Helpers

Target functions in `src/md_gen/config.py`:
- `_resolve_required_directory`
- `_resolve_output_directory`
- `_resolve_optional_file`

Required test cases:
- Valid existing directory resolves to an absolute `Path`.
- Missing source directory raises `ConfigValidationError` with the invalid-source code.
- File path passed to required-directory helper raises the same validation error.
- Missing output directory is created and returned.
- Existing output directory is returned unchanged.
- Simulated creation failure raises `ConfigValidationError` with the output-create error code.
- Optional file helper returns `None` for empty/absent inputs.
- Optional file helper resolves a real file path when provided.

Pseudo-flow:

```text
tmp_dir = temporary directory
existing_dir = tmp_dir / "source"
existing_dir.mkdir()

assert _resolve_required_directory(str(existing_dir)) == existing_dir.resolve()
assert _resolve_optional_file(None) is None

missing_output = tmp_dir / "output"
assert _resolve_output_directory(str(missing_output)) == missing_output.resolve()
assert missing_output.exists()
```

## 5.4 Cover Settings File Loading

Target function:
- `read_json_settings_file`

Required test cases:
- Existing JSON settings file is parsed successfully.
- Missing `settings.json` triggers copy from the default file path.
- Copy failure raises `ConfigValidationError` with the create-failed code.
- Bad JSON or unreadable settings file raises `ConfigValidationError` with the read-failed code.

Implementation notes:
- Monkeypatch `DEFAULT_SETTINGS_FILE` to point at a temporary file path.
- Use a temp directory containing a fake `settings-default.json` for the bootstrap case.
- Avoid touching the repository’s real config files.

Pseudo-flow:

```text
set DEFAULT_SETTINGS_FILE to tmp_path / "settings.json"
create tmp_path / "settings-default.json"
write valid json to default file

call read_json_settings_file()

assert copied settings file now exists
assert returned dict matches expected content
```

## 5.5 Cover Prompt Settings

Target function:
- `build_prompt_settings_from_args`

Required test cases:
- `summary_prompt` on the namespace is used when present.
- JSON config prompt path is used when namespace value is missing.
- Built-in fallback prompt is used when neither source provides a file path.
- Unreadable prompt file raises `ConfigValidationError` with the prompt-read-failed code.

Implementation notes:
- Provide prompt files in `tmp_path` for readable-path cases.
- Use `json_config` dict values to drive fallback ordering.
- Verify both `summary_prompt_path` and `summary_prompt_text` fields in the resulting dataclass.

Pseudo-flow:

```text
args = Namespace(summary_prompt=str(prompt_file))
json_config = {}
settings = build_prompt_settings_from_args(args, json_config)

assert settings.summary_prompt_path == prompt_file.resolve()
assert settings.summary_prompt_text == prompt_file.read_text()
```

## 5.6 Cover Llama Model Settings

Target function:
- `build_llama_model_settings_from_args`

Required test cases:
- Namespace values are used when present.
- JSON config values are used when namespace values are missing.
- Built-in defaults are used when both inputs omit timeout and retry values.
- Missing endpoint or model name raises the correct config validation error.

Implementation notes:
- Use `capsys` where needed to confirm the default branch emitted its informational message.
- Test both the endpoint/model required-path validation and the default fallbacks.

Pseudo-flow:

```text
args = Namespace(model_endpoint=None, model_name=None, timeout_seconds=None, max_retries=None)
json_config = {"endpoint": "http://...", "model": "..."}
settings = build_llama_model_settings_from_args(args, json_config)

assert settings.endpoint_url == json_config["endpoint"]
assert settings.model_name == json_config["model"]
assert settings.request_timeout_seconds == 120.0 or json_config value
assert settings.request_max_retries == 2 or json_config value
```

## 5.7 Cover Image Settings

Target function:
- `build_image_settings_from_args`

Required test cases:
- Namespace-provided values win over JSON config values.
- JSON config values are used when namespace values are missing.
- Built-in defaults are used when both inputs omit values.

Implementation notes:
- Test one case for provided namespace values and one for fallback/default paths.
- Assert the dataclass values directly.

## 5.8 Cover Full Config Assembly

Target function:
- `build_config_from_args`

Required test cases:
- A successful integration-style test with only the expected namespace attributes present.
- A failure-path test for invalid source path handling.
- A derived-path assertion showing `output/temp` is created from the output argument.

Recommended approach:
- Monkeypatch `read_json_settings_file` if needed to keep the test focused on assembly rather than bootstrap behavior.
- Reuse helper fixtures for namespace construction so the assembly test stays readable.

Pseudo-flow:

```text
args = Namespace(
    source=str(source_dir),
    output=str(output_dir),
    summary_prompt=None,
    ocr_model_endpoint=None,
    ocr_model_name=None,
    ocr_timeout_seconds=None,
    ocr_max_retries=None,
    language_model_endpoint=None,
    language_model_name=None,
    language_timeout_seconds=None,
    language_max_retries=None,
    max_longest_edge_px=None,
    token_threshold=None,
    dry_run=False,
    overwrite=False,
)

config = build_config_from_args(args)

assert config.paths.output_dir == output_dir.resolve()
assert config.paths.temp_dir == output_dir.resolve() / "temp"
```

## 6. Execution Order

1. Fix `pyproject.toml` so pytest discovers `test/` and coverage is measured against the intended module target.
2. Replace the stub in `test/md_gen/test_config.py` with direct unit tests for the helper functions.
3. Add the settings-file tests using temp files and monkeypatching.
4. Add prompt/model/image helper tests to cover fallback branches and defaults.
5. Add the `build_config_from_args` integration-style test.
6. Run the focused pytest command for `test/md_gen/test_config.py` and then the module coverage run.

## 7. Exit Criteria

This phase is complete when all of the following are true:
- `test/md_gen/test_config.py` contains real tests, not a stub.
- Every function in `src/md_gen/config.py` is covered by at least one test.
- The module coverage for `src/md_gen/config.py` is at least 80%.
- Pytest discovers tests under `test/` correctly.
- No test imports or executes `src/md_gen/cli.py`.

## 8. Validation Plan

Run focused validation in this order:

1. `pytest test/md_gen/test_config.py -q`
2. `pytest test/md_gen/test_config.py --cov=src/md_gen/config.py --cov-report=term-missing`
3. If the repo uses the standard project environment, run the same command through the project runner so it matches local development.

Success indicators:
- All config tests pass.
- Coverage output shows the module meets or exceeds 80%.
- No CLI parser or application bootstrap is required to pass the suite.

## 9. Risks and Mitigations

Risk: pytest still points to the wrong test root.
Mitigation: update `pyproject.toml` before validating the new test file.

Risk: filesystem bootstrap branches in `read_json_settings_file` are brittle.
Mitigation: isolate them with temp directories and monkeypatched module constants.

Risk: the module coverage threshold is measured too broadly.
Mitigation: make the coverage target explicit for `src/md_gen/config.py` rather than the entire source tree.

## 10. Handoff Notes

This plan feeds directly into implementation of the config test file and the pytest configuration correction. The next step after this plan is to add the tests and run the focused validation commands above.