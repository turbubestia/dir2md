# Issue 7 - Add Unit Test Coverage for md_gen Config

## 1. Goal

Add unit test coverage for `src/md_gen/config.py` that validates configuration assembly when the caller provides only the mandatory CLI arguments.

## 2. Functional Requirement

- The test suite must exercise `build_config_from_args` directly.
- Tests must construct the input with an `argparse.Namespace` or equivalent simple object.
- Tests must provide only the required CLI arguments:
  - `source`
  - `output`
- Tests must not call `src/md_gen/cli.py` or use `argparse.ArgumentParser.parse_args()`.

**User: we want to test all method in `config.py`, not just when only source and output is provided. We want to have at least 80% code coverage.**

## 3. Expected Behavior To Validate

- Mandatory path settings are resolved from the provided `source` and `output` values.
- `output/temp` is derived automatically from the provided output path.
- Optional settings fall back to their configured defaults when not supplied on the namespace.
- The configuration object is built successfully without requiring CLI parser behavior.

## 4. Constraints

- Keep the test focused on `src/md_gen/config.py` only.
- Do not couple the test to CLI parsing, command execution, or Foundation bootstrapping.
- The test should remain stable even if CLI argument definitions change, as long as the config builder contract remains the same.

## 5. Edge Cases

- Missing `source` or `output` should be treated as invalid input for the configuration builder contract.
- Non-directory `source` values should continue to fail validation through the config path resolution logic.
- The test should not assume network access or external services.

## 6. Acceptance Criteria

- A unit test exists for `src/md_gen/config.py` that covers the mandatory-arguments path.
- The test verifies the config builder works when only `source` and `output` are present.
- The test does not import or invoke `src/md_gen/cli.py` as part of the assertion path.

## Refinement Iteration 1

### 1. Updated Goal

Expand the `src/md_gen/config.py` test coverage so the module is tested comprehensively, not only for the mandatory-arguments path.

### 2. Updated Functional Requirement

- Add unit tests that exercise every public function in `src/md_gen/config.py`.
- Prefer direct function calls over CLI-level execution.
- Continue to avoid `src/md_gen/cli.py` and `argparse.ArgumentParser.parse_args()` in the test flow.
- Build test inputs with `argparse.Namespace` or a similarly minimal object when a function expects CLI-like attributes.

### 3. Updated Coverage Requirement

- The test suite for `src/md_gen/config.py` must reach at least 80% code coverage for that module.
- Coverage should be measured for the module itself, not only for the whole test suite.

### 4. Updated Behavior To Validate

- Path resolution helpers validate both valid and invalid inputs.
- Prompt-loading behavior is covered for default, override, and fallback scenarios.
- Model-setting helpers are covered for values coming from the namespace, JSON config, and built-in defaults.
- Image-setting helpers are covered for values coming from the namespace, JSON config, and built-in defaults.
- `build_config_from_args` is covered as the module-level integration point that combines the helper functions.

### 5. Updated Constraints

- Keep the tests localized to `src/md_gen/config.py`.
- Do not broaden scope to unrelated modules just to raise coverage.
- Preserve the current configuration contract while increasing test depth.

### 6. Updated Edge Cases

- Missing optional config values should continue to fall back to built-in defaults.
- Invalid source paths should continue to raise validation errors.
- Read failures for prompt files should continue to exercise the fallback behavior expected by the config module.

### 7. Updated Acceptance Criteria

- Every function in `src/md_gen/config.py` is covered by at least one test.
- The module reaches at least 80% coverage.
- The tests remain direct unit tests and do not depend on CLI parsing or application startup.