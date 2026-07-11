# Refinement Iteration 2

## 1. Goal

Define requirements to add comprehensive unit tests for `src/md_gen/discovery.py` in `test/md_gen/test_discovery.py`, with the intent to cover all module methods and branches.

## 2. Functional Requirements

- Add or update unit tests in `test/md_gen/test_discovery.py` so all callable methods in `src/md_gen/discovery.py` are exercised.
- Focus the tests on discovery behavior only, including file discovery, filtering, ordering, and work-item construction.
- Build `AppConfig` in tests via `build_config_from_args` for consistency with existing test patterns.
- Ensure test fixtures use a temporary source directory created by the tests, populated with dummy files representing supported and unsupported inputs.

## 3. Constraints

- Scope is limited to `src/md_gen/discovery.py`.
- Do not add or require tests for `src/md_gen/foundation.py` or other modules as part of this issue.
- Keep tests as deterministic unit tests with no network access and no dependency on external services.
- Do not depend on CLI parser execution (`parse_args`) in assertions.

## 4. Edge Cases To Cover

- Empty source directory.
- Source directory with only unsupported file extensions.
- Source directory with mixed supported and unsupported files.
- Case-variant file extensions and path normalization behavior.
- Nested directories and deterministic ordering of discovered items.
- Work item mapping for different supported source types (for example, PDF vs image inputs).

## 5. Acceptance Criteria

- `test/md_gen/test_discovery.py` covers every method in `src/md_gen/discovery.py`.
- Coverage target applies to `src/md_gen/discovery.py` only and reaches full line coverage.
- Tests construct `AppConfig` using `build_config_from_args` with a temporary source directory and test-created dummy files.
- Tests are offline, repeatable, and limited to discovery-module behavior.