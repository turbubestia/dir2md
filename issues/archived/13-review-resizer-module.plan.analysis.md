# Issue 13 - Review resizer module and add unit test for full coverage

## Analysis Objective

Define exactly what must change to satisfy [issues/13-review-resizer-module.plan.request.md](issues/13-review-resizer-module.plan.request.md), limited to:
- [src/md_gen/resizer.py](src/md_gen/resizer.py)
- [test/md_gen/test_resizer.py](test/md_gen/test_resizer.py)

This document describes required modifications and verification targets only. It does not prescribe implementation details.

## Current Architecture Snapshot

### Module under review

- [src/md_gen/resizer.py](src/md_gen/resizer.py) contains:
  - `ImageResizeResult` dataclass used as the observable output contract.
  - `_target_dimensions(width, height, max_longest_edge_px)` for long-edge constrained dimension planning.
  - `resize_image_for_ocr(source_image_path, output_dir, max_longest_edge_px)` for single-image processing, including in-place replacement when source is already in output.
  - `resize_images_for_ocr(source_image_paths, output_dir, max_longest_edge_px)` batch wrapper.

### Test module under review

- [test/md_gen/test_resizer.py](test/md_gen/test_resizer.py) currently tests selected behaviors for downscale/no-resize/in-place paths.
- The tests currently assert `result.is_valid_for_ocr`, but `ImageResizeResult` in [src/md_gen/resizer.py](src/md_gen/resizer.py) has no such field. This contract mismatch must be resolved within test scope.

## Requirement-to-Component Mapping

### R1. PDF-derived images already in output are conditionally resized in place

Affected components:
- `resize_image_for_ocr` in [src/md_gen/resizer.py](src/md_gen/resizer.py)
- Assertions in [test/md_gen/test_resizer.py](test/md_gen/test_resizer.py)

What must be validated/adjusted:
- Source-in-output detection logic must preserve same output path for in-place behavior.
- Branch behavior must be explicitly covered for:
  - in-place + needs resize => replace same file.
  - in-place + no resize => no rewrite side effects required by contract.
- Exact threshold boundary (`long_edge == max`) must be covered and treated as no-resize.

### R2. Source-folder images are resized-or-copied into output

Affected components:
- `resize_image_for_ocr` in [src/md_gen/resizer.py](src/md_gen/resizer.py)
- Assertions in [test/md_gen/test_resizer.py](test/md_gen/test_resizer.py)

What must be validated/adjusted:
- Non-output source path must map to output path in `output_dir`.
- Decision branches must be covered for:
  - non-output source + resize needed => resized artifact in output.
  - non-output source + no resize => copied artifact in output.
- Source image immutability expectation must be validated for non-output inputs.

### R3. Output completeness and OCR-ready sizing policy

Affected components:
- `_target_dimensions` and both public resize functions in [src/md_gen/resizer.py](src/md_gen/resizer.py)
- Batch and edge-case tests in [test/md_gen/test_resizer.py](test/md_gen/test_resizer.py)

What must be validated/adjusted:
- Long-edge policy is the single sizing criterion.
- No upscaling behavior for images already within constraints.
- Batch function returns complete per-input result set and deterministic mapping.
- Empty batch behavior should be verified explicitly.

## Contract and Data Structure Analysis

### `ImageResizeResult` observable contract

Current fields in [src/md_gen/resizer.py](src/md_gen/resizer.py):
- `source_image_path`
- `output_image_path`
- `original_width`, `original_height`
- `resized_width`, `resized_height`
- `was_resized`
- `max_longest_edge_px`

Required action at analysis level:
- Align tests in [test/md_gen/test_resizer.py](test/md_gen/test_resizer.py) with this current contract, or formally extend contract in [src/md_gen/resizer.py](src/md_gen/resizer.py) if project decision requires OCR validity flags. Because issue scope is resizer-only, either path is permissible, but one contract must be canonical and consistently tested.

### Path and file-write behavior

Observed write patterns in [src/md_gen/resizer.py](src/md_gen/resizer.py):
- Temporary file replacement path when resizing.
- Direct copy for non-resized, non-in-place case.
- No action for in-place non-resize case.

Required action at analysis level:
- Add/adjust tests to ensure each write branch is behaviorally covered and that output-file existence and dimensions match branch expectations.

## Test Coverage Gaps To Close

In [test/md_gen/test_resizer.py](test/md_gen/test_resizer.py), required additional or corrected coverage includes:
- Threshold equality case (`long_edge == max_longest_edge_px`).
- Portrait aspect ratio resize path (complementing landscape).
- Non-output source copy path verification (including preserved dimensions).
- In-place replacement verification when resize is required.
- `resize_images_for_ocr` batch behavior for mixed inputs (resize + copy/no-resize).
- Empty batch input behavior.
- Invalid/corrupt image behavior according to selected contract (error propagation vs tolerant handling).
- Removal or replacement of assertions against nonexistent `is_valid_for_ocr` unless that field is intentionally added to the result contract.

## Scope Boundaries and Non-Changes

Must not change:
- Any file outside [src/md_gen/resizer.py](src/md_gen/resizer.py) and [test/md_gen/test_resizer.py](test/md_gen/test_resizer.py).
- Rasterizer/discovery/CLI/merge module responsibilities.

## Open Design Decisions Requiring Confirmation

The following decisions affect what must be asserted in tests and therefore must be finalized before implementation completion:
- Canonical source of `max_longest_edge_px` for this module contract (call-site provided only vs coupled config assumptions in tests).
- Error contract for unreadable/corrupt images in single and batch functions (raise and stop vs skip/report pattern).
- Collision policy when source-folder image target path already exists in output (overwrite expected vs explicit conflict handling).

## Completion Criteria for Implementation Phase

The implementation phase can be considered complete when:
- Behavior in [src/md_gen/resizer.py](src/md_gen/resizer.py) matches R1-R3 from the request.
- [test/md_gen/test_resizer.py](test/md_gen/test_resizer.py) fully covers branch and edge behavior listed above.
- Test expectations are consistent with the finalized `ImageResizeResult` contract.
- No out-of-scope files are modified.
