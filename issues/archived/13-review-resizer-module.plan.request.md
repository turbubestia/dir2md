# Issue 13 - Review resizer module and add unit test for full coverage

The `src\md_gen\rasterizer.py` will generate images from the discovered PDF and place in the `output` folder. Meanwhile source images will still be in the `source` one. After this step we need to resize the images from the PDF already in the `output` folder and the original images still in the `source` one to a suitable size for OCR by the LightOnOCR-2 model.

## Goals

- Images from the PDF ware save to the `output` folder (by the `src\md_gen\rasterizer.py` module) will be resize if long edge it larger than the max edge size and replace the source pdf image, but is withing the size will remain untouched.
- Images in the `source` folder will be resize by the same policy and placed in the `output` folder, or just copied if they don't need to be resize.
- Have in the `output` folder all the pages in the suitable size.
- After the `src\md_gen\resizer.py` is verify to follow the requirements, we need to write tests in the `test\md_gen\test_resizer.py` file.
- No other module than `src\md_gen\resizer.py` will be review or tested.

# Refinement Iteration 1

## Scope

- In scope:
	- Requirement review and behavioral validation of `src/md_gen/resizer.py` only.
	- Unit test authoring and updates in `test/md_gen/test_resizer.py` only.
- Out of scope:
	- Any code or tests outside `src/md_gen/resizer.py` and `test/md_gen/test_resizer.py`.
	- Behavioral changes in rasterization, discovery, CLI orchestration, or merge modules.

## Functional Requirements

### R1. Resize PDF-derived images already in output

- Description:
	- Images previously generated from PDF pages and stored in `output` must be evaluated for resizing.
	- If an image long edge is greater than the configured maximum edge size, resize it and replace the existing file in `output`.
	- If the long edge is less than or equal to the maximum edge size, leave the image unchanged.
- Constraints:
	- Replacement must occur at the same logical output location (no duplicate copy for the same page).
	- Resize policy must be based on long-edge threshold only.
- Edge cases:
	- Long edge exactly equal to threshold: do not resize.
	- Very small images: no upscaling.
	- Single-page and multi-page PDF outputs must follow identical policy.

### R2. Process source-folder images into output

- Description:
	- Images present in `source` must be processed with the same long-edge threshold policy.
	- If resize is needed, write resized result to `output`.
	- If resize is not needed, copy source image to `output` unchanged.
- Constraints:
	- Source files in `source` must not be modified in place.
	- Final artifact for each source image must exist in `output`.
- Edge cases:
	- Mixed batches where some images need resize and others do not.
	- Existing file in `output` with same target name/path handling must be deterministic.

### R3. Output completeness for OCR readiness

- Description:
	- After resizer execution, all pages/images expected for OCR must be present in `output` and comply with the long-edge policy.
- Constraints:
	- No missing output files for inputs selected for processing.
	- Files that do not require resizing remain visually/data-equivalent to original copies.
- Edge cases:
	- Empty input set should complete without error and produce no unexpected output.
	- Corrupt or unreadable image behavior must be explicit (fail-fast or skip-with-report).

## Test Requirements

### T1. Unit test coverage target

- Description:
	- Add/adjust tests in `test/md_gen/test_resizer.py` to achieve full behavioral coverage for `src/md_gen/resizer.py` logic.
- Constraints:
	- Tests must focus on resizer behaviors only.
	- No new tests in other modules.
- Edge cases to include in tests:
	- Long edge greater than max edge.
	- Long edge equal to max edge.
	- Long edge below max edge.
	- Source image copied vs resized decision path.
	- In-place replacement behavior for PDF-derived output images.
	- Error-path behavior for invalid/unreadable images (according to current contract).

### T2. Regression and determinism

- Description:
	- Tests must validate deterministic output placement and decision logic across repeated runs.
- Constraints:
	- Assertions should not rely on nondeterministic file ordering.
	- Tests should isolate filesystem state per test case.

## Non-Functional Requirements

- Clarity:
	- Requirement wording must remain implementation-agnostic while being testable.
- Traceability:
	- Each test scenario should be traceable to at least one requirement (R1-R3, T1-T2).
- Maintainability:
	- Keep test suite concise and focused on public/observable behavior of `resizer.py`.

## Acceptance Criteria

- `src/md_gen/resizer.py` behavior conforms to R1-R3.
- `test/md_gen/test_resizer.py` covers all required decision branches and edge cases listed in T1.
- No modifications are made outside the two allowed files.

## Open Questions

- What is the authoritative max-edge configuration source/value for these requirements (fixed constant vs config-driven)?
- For unreadable/corrupt images, should processing stop with an error or skip and continue with reporting?
- When a `source` image maps to an existing target path in `output`, should overwrite always occur, or should collision handling follow a different rule?