# Issue 13 - Implementation Plan for Resizer Review and Full Unit Coverage

## Plan Goal

Deliver a complete, scoped implementation for Issue 13 by updating only:
- src/md_gen/resizer.py
- test/md_gen/test_resizer.py

This plan translates the analysis into actionable implementation phases without introducing out-of-scope changes.

## Scope Guardrails

- Allowed files:
  - src/md_gen/resizer.py
  - test/md_gen/test_resizer.py
- Forbidden changes:
  - Any other source or test file
  - CLI wiring, discovery, rasterizer, merge, config modules

## Decision Gate (Resolve Before Final Assertions)

Before finalizing tests, lock the following decisions. If no explicit decision is provided, use the default assumption shown here to proceed:

1. Result contract canonicalization:
- Decision: Keep ImageResizeResult as currently defined in resizer.py.
- Default assumption: Remove/replace test expectations for nonexistent fields (for example, is_valid_for_ocr) instead of extending the dataclass.

2. Error behavior for unreadable/corrupt images:
- Decision: Fail fast by propagating the PIL/open error.
- Default assumption: Single-image call raises; batch call raises at the failing item.

3. Output collision policy for source-folder images:
- Decision: Overwrite destination path deterministically when writing/copying.
- Default assumption: Existing target in output is replaced by current run result.

## Phase 1 - Normalize Observable Contract and Existing Tests

### Objective
Align tests with the canonical observable behavior exposed by resizer.py.

### Steps
1. Inspect ImageResizeResult fields and treat them as the single assertion surface.
2. Remove or replace invalid assertions in test_resizer.py that reference nonexistent attributes.
3. Ensure each existing test asserts only supported fields and file outcomes:
- was_resized
- original and resized dimensions
- output path resolution
- output file existence

### Pseudocode
```text
for each existing test in test_resizer.py:
  identify all result.<field> assertions
  if field not in ImageResizeResult:
    replace with equivalent observable assertion
    prefer dimensions/path/existence assertions
```

### Validation
- test_resizer imports and executes without attribute errors.
- Existing scenarios still validate the same intended behavior.

### Exit Criteria
- No test references nonexistent result attributes.
- Contract assertions are consistent across all tests.

## Phase 2 - Ensure Resizer Branch Coverage Against R1 and R2

### Objective
Cover all single-image decision branches in resize_image_for_ocr.

### Steps
1. Add or adjust tests for threshold boundaries:
- long edge greater than max: resize
- long edge equal to max: no resize
- long edge below max: no resize
2. Add portrait-oriented resize scenario to complement landscape scenario.
3. Add/verify in-place behavior when source is already in output:
- in-place + resize required: same path replaced
- in-place + no resize: same path preserved and dimensions unchanged
4. Add/verify non-output source behavior:
- resize path writes resized file to output
- no-resize path copies to output unchanged
5. Add immutability check for source-folder input files where processing writes to output.

### Pseudocode
```text
case matrix for resize_image_for_ocr:
  case A: source parent == output dir AND long edge > max
    expect output path == source path
    expect was_resized == true
    expect on-disk dimensions == computed target

  case B: source parent == output dir AND long edge <= max
    expect output path == source path
    expect was_resized == false
    expect dimensions unchanged

  case C: source parent != output dir AND long edge > max
    expect output path in output dir
    expect was_resized == true
    expect output dimensions reduced by long-edge rule
    expect source file dimensions unchanged

  case D: source parent != output dir AND long edge <= max
    expect output path in output dir
    expect was_resized == false
    expect output dimensions equal source dimensions
```

### Validation
- Every branch in resize_image_for_ocr is exercised by at least one test.
- Boundary test for equality confirms no resize.

### Exit Criteria
- Single-image behavior is fully covered for path and resize decisions.

## Phase 3 - Cover Batch and Edge Behaviors Against R3

### Objective
Validate resize_images_for_ocr completeness, determinism, and edge behavior.

### Steps
1. Add mixed-input batch test containing at least:
- one image requiring resize
- one image requiring copy/no-resize
2. Assert tuple length equals input length and ordering is preserved by position.
3. Assert per-item output paths and per-item was_resized flags are correct.
4. Add empty input batch test:
- input empty tuple returns empty tuple
5. Add corrupt/unreadable image test according to chosen error contract.

### Pseudocode
```text
given source_image_paths = (img_resize, img_copy)
results = resize_images_for_ocr(source_image_paths, output_dir, max_edge)
assert len(results) == 2
assert results[0] corresponds to img_resize behavior
assert results[1] corresponds to img_copy behavior

given source_image_paths = ()
results = resize_images_for_ocr(...)
assert results == ()

given corrupt image in input
expect exception behavior per decision gate
```

### Validation
- Batch tests prove deterministic positional mapping.
- Empty and failure-path behavior is explicit and reproducible.

### Exit Criteria
- Batch wrapper has clear coverage for normal, empty, and error-path scenarios.

## Phase 4 - Verification and Coverage Closure

### Objective
Confirm all requested coverage and scope constraints are satisfied.

### Steps
1. Run focused tests for resizer module.
2. Run full test_resizer.py to ensure no regressions in that file.
3. Confirm modified-file set is exactly the two allowed files.
4. Review assertions-to-requirements traceability:
- R1: in-place PDF-derived output behavior
- R2: source-folder copy/resize behavior
- R3: completeness and batch policy

### Validation Commands
```text
pytest test/md_gen/test_resizer.py -q
pytest test/md_gen/test_resizer.py --maxfail=1
```

### Exit Criteria
- test/md_gen/test_resizer.py passes.
- Branch and edge-case assertions align with Issue 13 requirements.
- No out-of-scope files changed.

## Todo Checklist

- [ ] Resolve or accept default assumptions in Decision Gate.
- [ ] Align current tests to canonical ImageResizeResult contract.
- [ ] Add missing single-image branch/boundary tests.
- [ ] Add missing batch mixed/empty/error-path tests.
- [ ] Execute tests and verify pass status.
- [ ] Confirm only two scoped files were modified.

## Definition of Done

Implementation is done when:
- Behavior in src/md_gen/resizer.py conforms to Issue 13 R1-R3.
- test/md_gen/test_resizer.py covers all branch and edge cases listed in this plan.
- Tests do not assert nonexistent contract fields.
- Only the scoped resizer source and test files are changed.
