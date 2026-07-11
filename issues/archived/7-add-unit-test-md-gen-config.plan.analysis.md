# Issue 7 - Add Unit Test Coverage for md_gen Config (Implementation Analysis)

## 1. Objective and Scope

This issue expands `src/md_gen/config.py` test coverage from a single-path config assembly check into a comprehensive unit test suite for the whole module.

Primary outcomes:
- Exercise every function in `src/md_gen/config.py`, including private helpers.
- Reach at least 80% coverage for the module.
- Keep the tests direct and isolated from CLI parsing and application startup.

Out of scope for this issue:
- Behavior changes in `src/md_gen/cli.py`.
- Foundation/bootstrap execution paths.
- Any broader md_gen or md_mrg feature work unrelated to config coverage.

## 2. Current State vs Target State

### 2.1 Current State (Problem)

- `test/md_gen/test_config.py` is effectively a stub and does not assert any behavior.
- The current request scope started with only the mandatory `source` and `output` path path, but the refinement now requires all config-module methods to be tested.
- `pyproject.toml` points pytest discovery at `tests`, while this repository uses `test/`.
- The existing coverage option is module-agnostic (`--cov=src`), which is too broad for a focused 80% target on `src/md_gen/config.py`.

### 2.2 Target State (Required)

- A real `test/md_gen/test_config.py` suite covers the full config module.
- The suite validates success and failure branches of the helper functions, not just the integration path.
- Test discovery works against the repository’s actual `test/` layout.
- Coverage can be measured against `src/md_gen/config.py` specifically, with an 80% minimum target.

## 3. Files and Modules That Need Attention

### 3.1 `test/md_gen/test_config.py`

This is the primary implementation file for the issue.

Required work:
- Replace the current import-only stub with real tests.
- Add direct unit tests for each function in `src/md_gen/config.py`:
  - `ConfigValidationError`
  - `_resolve_required_directory`
  - `_resolve_output_directory`
  - `_resolve_optional_file`
  - `read_json_settings_file`
  - `build_path_settings_from_args`
  - `build_prompt_settings_from_args`
  - `build_llama_model_settings_from_args`
  - `build_image_settings_from_args`
  - `build_config_from_args`
- Use `argparse.Namespace` or an equivalent simple object for CLI-like inputs.
- Keep the tests at the unit level and avoid importing or invoking `src/md_gen/cli.py`.

### 3.2 `pyproject.toml`

This file needs pytest configuration correction so the new tests are actually discovered and the coverage requirement is meaningful.

Required work:
- Update `testpaths` to match the repository’s real test directory (`test`).
- Revisit the coverage command so it measures `src/md_gen/config.py` rather than the entire `src` tree for this issue’s goal.
- Add or adjust a failure threshold so the config-module target is enforceable at 80%.

### 3.3 `src/md_gen/config.py`

No production code change is strictly required if the current helper boundaries remain testable through `tmp_path`, `monkeypatch`, and module-level constant overrides.

However, if tests expose an untestable branch or a hard-coded filesystem dependency that cannot be isolated cleanly, this module would be the only production code candidate for a narrow seam.

## 4. Required Behavioral Coverage

### 4.1 Path Resolution Helpers

- `_resolve_required_directory` needs coverage for:
  - a valid existing directory
  - a non-existent path
  - a file path passed where a directory is required
- `_resolve_output_directory` needs coverage for:
  - auto-creating a missing directory
  - returning an existing directory unchanged
  - raising the config validation error path when directory creation fails
- `_resolve_optional_file` needs coverage for:
  - `None`
  - an empty value
  - a real path that resolves successfully

### 4.2 Settings File Loading

- `read_json_settings_file` needs coverage for:
  - successful read of an existing settings file
  - first-run behavior when `settings.json` is missing and the default file must be copied
  - copy failure path for the default file bootstrap
  - read or JSON-parse failure path

This function is the main place where filesystem isolation matters. The test design should rely on temporary directories and monkeypatching the module-level settings file constant rather than touching the real repo config files.

### 4.3 Prompt Settings

- `build_prompt_settings_from_args` needs coverage for:
  - explicit `summary_prompt` provided on the namespace
  - prompt path coming from JSON config when CLI input is absent
  - built-in prompt fallback when no file path is provided
  - unreadable prompt file error handling

### 4.4 Model Settings

- `build_llama_model_settings_from_args` needs coverage for:
  - endpoint and model name provided by the namespace
  - endpoint and model name pulled from JSON config when namespace values are missing
  - timeout and retry values coming from namespace
  - timeout and retry values falling back to JSON config
  - hardcoded defaults when both namespace and JSON config omit the values

Because this helper prints informational messages when defaults are used, tests may need `capsys` to assert the default path was reached.

### 4.5 Image Settings

- `build_image_settings_from_args` needs coverage for:
  - namespace-provided values
  - JSON-provided values when namespace values are missing
  - hardcoded default values when both inputs omit the settings

### 4.6 Full Config Assembly

- `build_config_from_args` needs at least one integration-style test that verifies the helpers are composed correctly.
- The test should build a namespace with the required path arguments plus the model/image/runtime attributes that the function expects.
- The test should confirm the resulting dataclass structure and key derived values such as `output/temp`.

## 5. Test Design Constraints

- Tests should remain in `test/md_gen` to match the module boundary.
- Tests should not rely on CLI parsing behavior, because the goal is to validate the config module directly.
- Tests should not require network access, external services, or non-deterministic state.
- The suite should prefer small, explicit fixtures over a broad end-to-end setup, because hitting 80% coverage on this module depends on covering branches inside helper functions.

## 6. Coverage Strategy

- The current request now explicitly requires coverage of all methods in `config.py`, not only the mandatory-arguments path.
- To reach 80%, the test suite needs to cover both normal and fallback branches.
- Parameterized tests are likely the most efficient way to cover the combinations of namespace values, JSON config values, and default fallbacks without duplicating setup.
- Module-level coverage should be measured for `src/md_gen/config.py`, not only as part of a whole-repository aggregate.

## 7. Risks and Constraints

- The repository’s current pytest configuration points at the wrong test root, so the new tests may not run unless `pyproject.toml` is corrected.
- The global `--cov=src` setting is too broad for the stated 80% requirement if the intent is to measure the config module itself.
- `read_json_settings_file` is filesystem-sensitive, so it may require careful monkeypatching to exercise the bootstrap and failure branches safely.
- The current implementation contains hard-coded default behavior and informational `print` calls; tests should validate observable outcomes without depending on incidental output formatting unless it is part of the branch under test.

## 8. Validation Criteria

This analysis is complete when the implementation plan can reasonably answer yes to all of the following:
- The config test file is converted from a stub into real unit tests.
- Every function in `src/md_gen/config.py` is covered by at least one test.
- The module reaches at least 80% coverage.
- Pytest discovery is aligned with the repository’s `test/` layout.
- The tests remain direct unit tests and do not depend on CLI parsing or bootstrap execution.