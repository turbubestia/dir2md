# Issue 9 - Add Unit Test Coverage for md_gen Discovery (Implementation Analysis)

## 1. Objective and Scope

This issue is limited to adding and completing unit-test coverage for `src/md_gen/discovery.py` in `test/md_gen/test_discovery.py`.

Required outcomes:
- Cover all callable methods and branch paths in `src/md_gen/discovery.py`.
- Use `build_config_from_args` to construct `AppConfig` instances in tests.
- Keep tests deterministic, local, and offline.

Out of scope:
- `src/md_gen/foundation.py` and any other module outside discovery.
- CLI parser execution behavior (`parse_args`) as part of test assertions.
- Network or gateway integration behavior.

## 2. Current State vs Target State

### 2.1 Current State

- `test/md_gen/test_discovery.py` currently contains only imports and no assertions.
- `src/md_gen/discovery.py` contains the discovery logic and work-item mapping, but currently has two definitions of `build_work_items` with different signatures.
- The second `build_work_items(config: AppConfig)` definition shadows the first `build_work_items(files: tuple[Path, ...])`, which introduces an internal recursion hazard and removes direct access to the tuple-based conversion function.

### 2.2 Target State

- `test/md_gen/test_discovery.py` becomes a complete unit-test suite for discovery behavior and branch coverage.
- Tests validate file support filtering, deterministic ordering, status emission, source-type assignment, and work-item construction.
- Config objects in tests are created through `build_config_from_args` with temporary directories and test-created dummy files.
- The duplicate-symbol condition in discovery is accounted for in issue execution, because full module coverage requires executable, reachable branch paths.

## 3. Files and Modules Requiring Changes

### 3.1 `test/md_gen/test_discovery.py`

This is the primary file that must be implemented.

Required test coverage areas:
- `_ordering_key`
- `_print_discovery_status`
- `_is_supported_file`
- `discover_supported_files`
- `_source_type_for_file`
- exported `build_work_items` behavior as currently defined

Required fixture and setup patterns:
- Use temporary source/output directories.
- Create dummy files with supported and unsupported extensions.
- Build `AppConfig` via `build_config_from_args` (namespace-like test input), not via handwritten config dataclass construction.

### 3.2 `src/md_gen/discovery.py`

This file is the test target and has a structural naming conflict that affects coverage viability.

Architecture finding that must be reflected in implementation scope:
- Two functions named `build_work_items` exist:
  - tuple-input conversion function
  - config-input orchestration function
- Because of name shadowing, the orchestration function calls itself with tuple input, which does not match its own expected config contract.

Implication for this issue:
- Full coverage and stable tests require this symbol conflict to be resolved or explicitly handled as part of the same issue workflow; otherwise, relevant branch paths are not testable as intended.

**User: This is an easy fix, I will correct this before going to the next step. So asumme for the implementation plan this fix will be in place.**

## 4. Behavioral Coverage Requirements

### 4.1 File Discovery and Filtering

- Verify supported extensions are consumed.
- Verify unsupported files are skipped with the correct reason.
- Verify directories are skipped with the correct reason.
- Verify empty-source behavior returns an empty tuple.

### 4.2 Ordering and Normalization

- Verify deterministic ordering by lowercase file name key.
- Verify case-variant extension handling (`.PDF`, `.JPG`, `.JPEG`, `.PNG`) through `.suffix.lower()` behavior.
- Verify only top-level source directory entries are considered.

### 4.3 Work Item Mapping

- Verify `pdf` vs `image` source type mapping.
- Verify `order_index` sequencing reflects sorted file order.
- Verify `ordering_key` field equals lowercase file name for each work item.

### 4.4 Observability Paths

- Verify status output format for consumed and skipped entries.
- Verify reason tokens for skip categories (`not_a_file`, `unsupported_extension`).

## 5. Data Structures and Logic Impact

Relevant structures and contracts under test:
- `WorkItem` dataclass fields:
  - `source_path: Path`
  - `source_type: Literal["pdf", "image"]`
  - `order_index: int`
  - `ordering_key: str`
- Extension classification constants:
  - PDF set
  - image set
  - combined supported set

Logic paths requiring branch-level assertions:
- `_is_supported_file`: file check and extension check together.
- `discover_supported_files`: consumed/skip branch split.
- `_source_type_for_file`: PDF branch and non-PDF branch.
- `build_work_items`: discovery-to-mapping orchestration path.

## 6. Risks and Constraints

- Duplicate function-name shadowing in discovery is a functional risk that may block straightforward full-coverage validation.
- Test scope must remain discovery-only despite the module-level defect; avoid introducing unrelated module changes.
- Tests must avoid dependence on environment-specific files or repository-local mutable state.

## 7. Validation Criteria

This analysis is complete when the implementation can satisfy all of the following:
- `test/md_gen/test_discovery.py` is converted from stub imports to real unit tests.
- All callable logic in `src/md_gen/discovery.py` is exercised, including edge-case branches from the request plan.
- `AppConfig` setup in discovery tests uses `build_config_from_args` with temp directories and dummy files.
- Coverage target is validated against `src/md_gen/discovery.py` only, not unrelated modules.