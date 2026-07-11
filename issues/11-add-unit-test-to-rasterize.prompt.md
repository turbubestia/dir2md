# Implementation Plan Iteration 1

## Scope Lock
- Modify only: test/md_gen/test_rasterizer.py
- Validate only module behavior in: src/md_gen/rasterizer.py
- Do not add tests for any other production module.
- Do not change production code unless a hard blocker is proven.

## Strategy Choices (Resolved for This Plan)
- Error-path strategy: Option A (fully controlled mocked/fake pdfium failure paths for deterministic branch coverage).
- Resource-lifecycle assertions: Option A (explicit close-call assertions with test doubles).

## Phase 0 - Baseline and Guardrails

### Goal
- Establish current baseline behavior and ensure edits remain scope-limited.

### Steps
1. Open and inspect test/md_gen/test_rasterizer.py to identify reusable helpers and naming style.
2. Record current tests and map each to rasterizer functions.
3. Ensure no edits are planned outside this file.

### Exit Criteria
- A branch checklist exists in working notes mapping all rasterizer branches to target tests.

### Validation
- Manual review confirms only one test file is in edit scope.

## Phase 1 - Test Infrastructure in test_rasterizer.py

### Goal
- Add deterministic local helpers/fakes required to drive success and failure branches.

### Steps
1. Keep or improve runtime PDF generator helper using PIL image save to PDF.
2. Add WorkItem factory helper to reduce repetition.
3. Add fake classes for controlled pdfium behavior:
   - FakeDocument with __len__, get_page(index), close().
   - FakePage with render(scale), close().
   - FakeBitmap with to_pil().
   - FakeImage with size, save(path, format), close().
4. Add lightweight call-tracking structures for close/save assertions.

### Pseudocode
```text
helper make_work_item(path, source_type="pdf", order_index=0, ordering_key=None):
    return WorkItem(...)

class FakeDocument:
    init(pages_or_error)
    __len__ -> total pages
    get_page(i) -> FakePage
    close() -> mark closed

class FakePage:
    init(render_result_or_error)
    render(scale):
        record scale
        if configured error: raise PdfiumError-like error
        return FakeBitmap
    close() -> mark closed
```

### Exit Criteria
- Helpers/fakes can model: open failure, render failure, zero-page doc, normal page flow.

### Validation
- Static check in file review: all new helpers are used by tests (no dead helper clutter).

## Phase 2 - Expand Unit Tests for Helper Functions

### Goal
- Cover pure helper branches completely.

### Steps
1. Add classifier tests covering all outcomes:
   - "password" or "encrypted" -> encrypted_pdf
   - "data format" or "syntax" -> corrupted_pdf
   - unrelated text -> unreadable_pdf
2. Add test for _build_output_image_path:
   - verifies output_dir join
   - verifies stem-pNNNN.png format
   - verifies stem with spaces/symbols is handled correctly

### Pseudocode
```text
test_classify_error_message_parametrized(message, expected_code):
    assert _classify_pdfium_error_message(message) == expected_code

test_build_output_image_path_formats_name(tmp_path):
    source = tmp_path / "sample doc(1).pdf"
    out = tmp_path / "im-temp"
    p = _build_output_image_path(source, 7, out)
    assert p == out / "sample doc(1)-p0007.png"
```

### Exit Criteria
- All branches of classifier function are explicitly asserted.
- Output path builder format and parent directory behavior are asserted.

### Validation
- Coverage report later shows helper functions at 100% statements.

## Phase 3 - Strengthen rasterize_pdf_work_item Success Path

### Goal
- Validate complete metadata propagation and artifact generation for real generated PDFs.

### Steps
1. Keep runtime PDF creation in tmp_path (single test with multi-page pdf).
2. Call rasterize_pdf_work_item with non-default work_item metadata values.
3. Assert:
   - page_index, page_number, total_pages sequence
   - source_order_index and source_ordering_key propagation
   - source_pdf_path propagation
   - image_path naming and parent directory
   - image_width and image_height match generated pages
   - output_dir is created when absent

### Pseudocode
```text
test_rasterize_work_item_success_metadata(tmp_path):
    pdf = create_pdf_with_pages([(300,120), (200,200)])
    work_item = make_work_item(pdf, order_index=3, ordering_key="k")
    pages = rasterize_pdf_work_item(...)
    assert len(pages) == 2
    assert [p.image_width for p in pages] == [300, 200]
    assert [p.image_height for p in pages] == [120, 200]
    assert all(p.image_path.parent == output_dir)
```

### Exit Criteria
- Success path assertions include dimensions and metadata fields, not only file existence.

### Validation
- Test passes without relying on repository PDF fixtures.

## Phase 4 - rasterize_pdf_work_item Failure and Edge Paths

### Goal
- Cover missing input, open-failure classification, render-failure classification, and zero-page behavior with deterministic tests.

### Steps
1. Missing input test:
   - pass non-existent source path
   - assert PdfRasterizationError.error_code == missing_input and source_path match
2. Open failure tests via monkeypatch on rasterizer.pdfium.PdfDocument:
   - raise PdfiumError-like exception message for encrypted/corrupted/unreadable
   - assert mapped error_code in raised PdfRasterizationError
3. Render failure test via fake document/page:
   - page.render raises PdfiumError-like exception
   - assert wrapped PdfRasterizationError has expected code
   - assert page.close and document.close were called
4. Zero-page test via fake document with len == 0:
   - assert returned tuple is empty
   - assert document.close called

### Pseudocode
```text
test_open_failure_maps_error(monkeypatch, tmp_path):
    pdf = create_valid_pdf(tmp_path)
    monkeypatch PdfDocument to raise PdfiumError("Incorrect password")
    with raises(PdfRasterizationError) as exc:
        rasterize_pdf_work_item(...)
    assert exc.value.error_code == "encrypted_pdf"

test_render_failure_closes_resources(monkeypatch, tmp_path):
    fake_doc = FakeDocument(with FakePage(render_error="syntax error"))
    monkeypatch PdfDocument -> fake_doc
    expect PdfRasterizationError("corrupted_pdf")
    assert fake_page.closed is True
    assert fake_doc.closed is True
```

### Exit Criteria
- All exceptional branches in rasterize_pdf_work_item are exercised.
- Close behavior is asserted in exceptional and zero-page flows.

### Validation
- Tests verify both error code mapping and source_path propagation.

## Phase 5 - Cover rasterize_pdf_work_items Aggregator

### Goal
- Cover filtering and flattening behavior in rasterize_pdf_work_items.

### Steps
1. Create mixed WorkItem tuple with source_type values including pdf and non-pdf.
2. Monkeypatch rasterize_pdf_work_item to deterministic stub returning known page tuples per pdf item.
3. Assert:
   - non-pdf items are skipped
   - per-pdf calls occur in input order
   - aggregated result tuple preserves flatten order
   - render_scale and output_dir are forwarded unchanged

### Pseudocode
```text
test_rasterize_work_items_filters_and_flattens(monkeypatch, tmp_path):
    calls = []
    def fake_rasterize(work_item, output_dir, render_scale):
        calls.append((work_item.source_path.name, output_dir, render_scale))
        return tuple_of_marker_pages

    monkeypatch rasterize_pdf_work_item = fake_rasterize
    result = rasterize_pdf_work_items((pdf1, png1, pdf2), out, render_scale=3.5)

    assert calls == [(pdf1,...,3.5), (pdf2,...,3.5)]
    assert result == expected_flattened_tuple
```

### Exit Criteria
- Both continue path (non-pdf) and extend path (pdf) are covered.

### Validation
- Aggregated ordering is explicitly asserted.

## Phase 6 - Execute and Verify Coverage

### Goal
- Demonstrate test success and full coverage target for rasterizer module.

### Steps
1. Run targeted tests for test/md_gen/test_rasterizer.py.
2. Run coverage command constrained to src/md_gen/rasterizer.py.
3. If coverage < 100%, inspect uncovered lines and add missing branch-focused tests in same file.
4. Re-run tests and coverage until target is met.

### Command Plan
```text
pytest test/md_gen/test_rasterizer.py -q
pytest test/md_gen/test_rasterizer.py --cov=src/md_gen/rasterizer.py --cov-report=term-missing
```

### Exit Criteria
- All rasterizer tests pass.
- Coverage output reports full statement coverage for src/md_gen/rasterizer.py.

### Validation
- Confirm no new/changed tests outside test/md_gen/test_rasterizer.py.

## Phase 7 - Final QA Checklist

### Checklist
- Only one test file modified: test/md_gen/test_rasterizer.py
- Runtime-generated PDFs used for source documents.
- No repository binary fixture dependency.
- Error mapping branches fully covered.
- Success and failure flows covered.
- Aggregator filtering and flattening covered.
- Full rasterizer coverage achieved and documented.

## Risks and Mitigations
- Risk: pdfium exception construction may be hard to instantiate directly.
- Mitigation: Use monkeypatch with compatible exception type or wrapped fake that triggers existing handler paths by message text.

- Risk: Real rasterization dimensions might vary in edge environments.
- Mitigation: Keep one real success test with robust assertions and use deterministic fakes for branch-specific internals.

## Definition of Done
- test/md_gen/test_rasterizer.py is updated, deterministic, and scoped to rasterizer behavior only.
- Source PDFs are created at runtime by tests.
- Coverage for src/md_gen/rasterizer.py reaches 100% statements.
- Test suite passes locally in project environment on Windows.
