# Issue 9 - Implementation Plan (md_gen Discovery Test Coverage)

Analysis file: `issues/9-add-unit-test-to-discovery.plan.analysis.md`

Assumption for this plan:
- The duplicate `build_work_items` naming conflict in `src/md_gen/discovery.py` is already corrected before implementation starts.

## 1. Phase Goal

Deliver a complete unit test suite in `test/md_gen/test_discovery.py` that exercises all callable logic and branch paths in `src/md_gen/discovery.py`, using `build_config_from_args` for config creation and achieving full discovery-module line coverage.

## 2. Scope of This Phase

In scope:
- Replace the current `test/md_gen/test_discovery.py` stub with real tests.
- Cover discovery helper behavior, file filtering, ordering, source-type mapping, and work-item construction/orchestration.
- Validate edge cases defined in the request and analysis.
- Measure coverage for `src/md_gen/discovery.py` only.

Out of scope:
- Adding or changing tests for `src/md_gen/foundation.py`.
- Network/gateway integration tests.
- CLI parser execution flow validation (`parse_args`).

## 3. Preconditions and Dependencies

- `src/md_gen/discovery.py` exposes callable paths that are no longer blocked by duplicate-name recursion.
- Test runtime has pytest available in the project environment.
- Temporary filesystem fixtures (`tmp_path`) are used for all input setup.

## 4. Implementation Workstreams

## 4.1 Build Test Scaffolding in `test/md_gen/test_discovery.py`

Target file:
- `test/md_gen/test_discovery.py`

Required setup tasks:
- Add imports for:
  - `argparse.Namespace`
  - `pathlib.Path`
  - `pytest` and optional fixtures (`tmp_path`, `capsys`)
  - `build_config_from_args`
  - discovery module symbols under test
- Create helper utilities in the test file to:
  - build a minimal Namespace accepted by `build_config_from_args`
  - create temp source/output dirs
  - create dummy files with chosen names/extensions

Pseudo-code scaffold:

**User: we don't need to pass all arguments to build_config_from_args, only the source and output directories are required for discovery tests.**

```text
def make_args(source_dir, output_dir, overrides=None):
    base = {
      "source": str(source_dir),
      "output": str(output_dir),
    }
    apply overrides
    return Namespace(**base)

def make_config(tmp_path, filenames):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "output"
    create dirs
    create each file under source_dir
    args = make_args(source_dir, output_dir)
    return build_config_from_args(args), source_dir, output_dir
```

Exit criteria:
- Test module has reusable setup primitives.
- All tests use `build_config_from_args` to obtain `AppConfig`.

## 4.2 Add Helper-Level Tests for Deterministic Behavior

Target functions in `src/md_gen/discovery.py`:
- `_ordering_key`
- `_source_type_for_file`
- `_is_supported_file`
- `_print_discovery_status`

Required test cases:
- `_ordering_key`
  - returns lowercase filename key
  - independent of parent directory path
- `_source_type_for_file`
  - `.pdf` maps to `pdf`
  - image extensions map to `image`
- `_is_supported_file`
  - supported file extensions return true
  - unsupported file extension returns false
  - directory path returns false
- `_print_discovery_status`
  - output contains `DISCOVERY status=... path=...`
  - `reason=` appears only when reason is provided

Pseudo-code block:

```text
create file "A.PDF" and "b.jpg" and "c.txt"
assert _ordering_key(Path("/x/A.PDF")) == "a.pdf"
assert _source_type_for_file(pdf_path) == "pdf"
assert _source_type_for_file(jpg_path) == "image"
assert _is_supported_file(pdf_path) is True
assert _is_supported_file(txt_path) is False
assert _is_supported_file(source_dir) is False

_print_discovery_status(pdf_path, status="consumed")
capture stdout and assert expected tokens
```

Exit criteria:
- Each helper has at least one positive and one negative/alternative path assertion where applicable.

## 4.3 Add Discovery Filtering and Ordering Tests

Target function:
- `discover_supported_files`

Required edge-case coverage:
- Empty source directory returns empty tuple.
- Source with only unsupported files returns empty tuple and skip statuses.
- Mixed supported/unsupported files returns only supported files.
- Mixed case extensions are accepted for supported types.
- Nested directories are skipped as `not_a_file` (top-level only behavior).
- Returned files are deterministic by lowercase filename ordering.

Pseudo-code block:

```text
build config with files:
  ["02-note.txt", "01-file.PDF", "03-photo.JPEG", "folder/"]
call discover_supported_files(config)
assert tuple contains only resolved paths for 01-file.PDF and 03-photo.JPEG
assert order is by lowercase filename key
assert captured stdout includes skipped reason for txt and folder
```

Exit criteria:
- `discover_supported_files` branch behavior is fully asserted (consumed, skipped-directory, skipped-extension).

## 4.4 Add Work Item Construction/Orchestration Tests

Target function(s):
- exported `build_work_items` behavior after the user-applied fix

Required assertions:
- Work item count equals discovered supported file count.
- Each work item contains:
  - resolved `source_path`
  - correct `source_type` (`pdf` or `image`)
  - sequential `order_index` starting at 0
  - lowercase `ordering_key`
- Ordering of work items follows discovery ordering guarantees.

Pseudo-code block:

```text
build config with files:
  ["B.JPG", "a.pdf", "ignore.md"]
work_items = build_work_items(config)
assert len(work_items) == 2
assert work_items[0].ordering_key == "a.pdf"
assert work_items[0].source_type == "pdf"
assert work_items[0].order_index == 0
assert work_items[1].ordering_key == "b.jpg"
assert work_items[1].source_type == "image"
assert work_items[1].order_index == 1
```

Exit criteria:
- WorkItem field contracts are validated end-to-end from discovery inputs.

## 4.5 Coverage and Validation Run

Validation commands (project environment):

```text
pytest test/md_gen/test_discovery.py -q
pytest test/md_gen/test_discovery.py --cov=src/md_gen/discovery.py --cov-report=term-missing
```

Validation expectations:
- Test file passes with no failures.
- Coverage report for `src/md_gen/discovery.py` reaches full line coverage target.
- No tests rely on network, gateways, or CLI parser execution.

Exit criteria:
- Acceptance criteria from the request and analysis are met and reproducible.

## 5. Ordered Todo List

1. Replace `test/md_gen/test_discovery.py` stub with test scaffolding and imports.
2. Add helper-function tests (`_ordering_key`, `_source_type_for_file`, `_is_supported_file`, `_print_discovery_status`).
3. Add `discover_supported_files` tests for empty, unsupported-only, mixed, case-variant, and nested-dir scenarios.
4. Add `build_work_items` orchestration tests for type mapping, order index, and ordering key correctness.
5. Run focused pytest for the discovery test module.
6. Run discovery-module coverage command and verify full coverage.
7. If coverage gaps remain, add narrowly scoped tests for uncovered branches and rerun validation.

## 6. Definition of Done

This implementation plan is complete when all of the following are true:
- `test/md_gen/test_discovery.py` contains full discovery-focused unit tests.
- `AppConfig` in tests is always created using `build_config_from_args` with temp directories and dummy files.
- `src/md_gen/discovery.py` branch paths and callable logic are fully covered.
- Coverage check against `src/md_gen/discovery.py` reaches full line coverage.
- Scope remains limited to discovery-module testing only.