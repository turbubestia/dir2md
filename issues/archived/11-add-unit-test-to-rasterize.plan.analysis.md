# Analysis Iteration 1

## Input Reference
- Source request analyzed: issues/11-add-unit-test-to-rasterize.plan.request.md
- User scope: Update/fix/extend tests only for src/md_gen/rasterizer.py using test/md_gen/test_rasterizer.py, create source PDFs in tests, and target full coverage for rasterizer module.

## Architecture Impact (What Must Change)

### Primary file to change
- test/md_gen/test_rasterizer.py

### Production module under test
- src/md_gen/rasterizer.py

### Existing dependent type used by tests
- src/md_gen/discovery.py (WorkItem dataclass/type usage only; no discovery behavior testing)

### No required production-code modifications identified
- Current requirement can be satisfied by test expansion only.
- If coverage uncovers unreachable defensive paths caused by external library behavior, that should be documented before considering production changes.

## Rasterizer Surface That Must Be Covered

### Functions
- _classify_pdfium_error_message(message)
- _build_output_image_path(source_pdf_path, page_number, output_dir)
- rasterize_pdf_work_item(work_item, output_dir, render_scale)
- rasterize_pdf_work_items(work_items, output_dir, render_scale)

### Types/behavior
- PdfRasterizationError creation and exposed fields (source_path, error_code)
- PdfPageRaster metadata for every emitted page

## Current Coverage Gaps in test/md_gen/test_rasterizer.py
- Missing direct validation of _build_output_image_path path format behavior.
- _classify_pdfium_error_message does not cover corrupted and default/unreadable branches.
- rasterize_pdf_work_item success path lacks explicit checks for image dimensions and render scale propagation.
- rasterize_pdf_work_item does not currently exercise page render failure branch (error classification from rendering stage).
- rasterize_pdf_work_item does not currently validate document with zero pages.
- rasterize_pdf_work_items is not covered:
  - Iteration over multiple WorkItem values.
  - Non-pdf filtering branch (continue path).
  - Aggregation ordering across multiple pdf inputs.

## Required Test Additions and Adjustments

### 1. Keep and strengthen successful PDF rasterization test
- Continue runtime PDF generation in temp directory.
- Expand assertions to include:
  - image_width and image_height values match generated source pages.
  - output path parent is output_dir.
  - source_ordering_key propagation.
  - output_dir creation behavior when directory does not pre-exist.

### 2. Add classifier branch-completeness tests
- Add separate tests or parametrized test for message mapping:
  - password/encrypted -> encrypted_pdf
  - data format/syntax -> corrupted_pdf
  - unrelated error text -> unreadable_pdf

### 3. Add output path builder test
- Validate naming pattern stem-pNNNN.png.
- Validate it preserves output directory and supports stem with spaces/symbols.

### 4. Add rasterize_pdf_work_item error-path tests
- Missing source path -> PdfRasterizationError with error_code missing_input and correct source_path.
- Open failure path classification:
  - Use controlled mocking/monkeypatch of pdfium.PdfDocument to raise PdfiumError-like error text and verify mapping to encrypted/corrupted/unreadable.
- Render failure path classification:
  - Mock page.render to raise PdfiumError-like text and verify wrapped PdfRasterizationError fields.
- Resource handling assertions:
  - Ensure page.close and document.close occur in exceptional flows (using fakes/spies).

### 5. Add zero-page document behavior test
- Simulate len(document) == 0 via fake document.
- Verify function returns empty tuple and still closes document.

### 6. Add rasterize_pdf_work_items coverage tests
- Multiple items with mixed source_type values:
  - pdf entries are rasterized.
  - non-pdf entries are skipped.
- Verify call ordering and final flattened tuple ordering.
- Verify render_scale and output_dir are forwarded to per-item calls.

### 7. Maintain strict module scope
- Tests may instantiate WorkItem as input contract only.
- Do not add assertions that validate discovery module logic.

## Data/Fixture Strategy Required
- Source PDFs must be generated during tests at runtime.
- Prefer in-test PDF creation via PIL for real success-path rasterization tests.
- Use test doubles/fakes for pdfium objects on exceptional or branch-specific paths to avoid nondeterminism and external dependency behavior drift.
- Use tmp_path for all filesystem outputs and isolation.

## Validation and Completion Criteria
- Execute targeted tests in test/md_gen/test_rasterizer.py.
- Execute coverage focused on src/md_gen/rasterizer.py and confirm full statement coverage.
- Confirm no new tests were added for modules outside rasterizer scope.

## Open Design Choices Needing Confirmation
1. Error-path strategy:
- Option A: Fully mocked pdfium failures for deterministic branch control.
- Option B: Hybrid with some real invalid files plus mocked render failures.

2. Resource-lifecycle assertions:
- Option A: Explicitly assert close-call behavior with fakes/spies.
- Option B: Implicit behavior only via successful completion and exceptions.
