# Implementation Plan: ocr-group-editable-tree

> **Core Objective:** Detailed step-by-step technical execution blueprint for implementing the requirements specified in the analysis.

> **Analysis Reference:** [Analysis Reference](./ocr-group-editable-tree.plan.analysis.md)
> **Traceability Scope:** This plan implements Analysis Sections 1, 2, 3, and 4. Each phase and step cites the specific analysis section it executes.

## Phase 1: Backend Editable Plan Models and Contracts

**Traceability:** Implements Analysis Sections 1, 2 (`src/webapp/backend/models.py`), and 3 (`Data Contract Compatibility`, `Error Handling`).

### Steps

1. In `src/webapp/backend/models.py`, add discriminated Pydantic models for editable merge-plan rows without changing the on-disk `batch_mrg.json` contract.
   - Reference: Analysis Section 2, `models.py` structural changes.
   - Add model types equivalent to:
     - `EditablePlanDocumentBase`: common artifact fields `id`, `source_file_name`, `file_type`, `markdown_file`, `page_count`, `date_of_process`, `summary`, `status`, plus unknown metadata.
     - `EditableImagePage`: `kind: Literal["image_page"]`, `file_type: Literal["image"]`.
     - `EditablePdfDocument`: `kind: Literal["pdf"]`, `file_type: Literal["pdf"]`.
     - `EditableImageGroup`: `kind: Literal["image_group"]`, `id`, `display_name`, `documents: list[EditableImagePage]`.
     - `EditableMergePlan`: `items: list[EditableImageGroup | EditablePdfDocument]` and optional `source_file_name`/metadata only if required by persisted plan shape.
     - `MarkdownPreviewResponse`: `id`, `markdown_file`, `content`.
   - Configure document models to preserve unknown metadata with Pydantic v2 `model_config = ConfigDict(extra="allow")` so planner/OCR fields round-trip.
   - Keep `WorkflowState` unchanged unless implementation chooses to embed the plan in server-sent workflow events; prefer dedicated endpoints to avoid overwriting in-progress client edits during routine state refreshes.

2. Add model-level validation for invalid editable-plan payloads.
   - Reference: Analysis Sections 2 and 3, model validation and error handling.
   - Reject empty `EditableImageGroup.documents`.
   - Reject non-image children in image groups by typing `EditableImagePage.file_type` as `Literal["image"]`.
   - Reject image pages as top-level items by only allowing `EditableImageGroup | EditablePdfDocument` in the top-level list.
   - Reject duplicate page/PDF identities in `EditableMergePlan` using a model validator keyed by stable document id.

**Exit Criterion:** Backend schemas can represent image groups, image pages, and standalone PDFs with preserved unknown metadata, and invalid empty/duplicate/misplaced documents fail Pydantic validation.

**Validation Command:** `uv run pytest test/webapp_tests/test_workflow_api.py -q`

## Phase 2: Backend Plan Loading, Saving, and Artifact Resolution

**Traceability:** Implements Analysis Sections 1, 2 (`src/webapp/backend/workflow.py`), and 3 (`Security & Permissions`, `Data Contract Compatibility`, `State Consistency`).

### Steps

1. In `src/webapp/backend/workflow.py`, add helpers for configured output directory validation.
   - Reference: Analysis Sections 2 and 3, output-folder and filesystem-boundary requirements.
   - Add `_resolve_output_dir(settings: AppSettings) -> Path` that rejects empty output folders, missing folders, non-directories, and inaccessible paths with `WorkflowServiceError` status codes.
   - Reuse this helper from plan and artifact routes; do not broaden source preview behavior.

2. Add conversion helpers from persisted `batch_mrg.json` to editable UI shape.
   - Reference: Analysis Sections 1, 2, and 3, data flow and apply compatibility.
   - Implement `_load_merge_plan_payload(output_dir: Path) -> dict[str, Any]` reading `md_mrg.planner.MERGE_PLAN_FILE_NAME`.
   - Implement `_editable_plan_from_payload(payload: dict[str, Any]) -> EditableMergePlan`.
   - Treat top-level items with a `documents` list as image groups, and top-level non-group records with `file_type == "pdf"` as standalone PDFs.
   - Derive stable row ids from persisted artifact fields without writing ids to `batch_mrg.json`; suggested page/PDF id input is `source_file_name` plus `markdown_file`, encoded with existing URL-safe base64 helper style.
   - Generate display-only group ids/names as `group-{index}` and `DocumentGroup_{index}` in current top-level order.
   - Reject malformed plans: non-object root, missing/non-list `documents`, empty groups, PDFs inside groups, image documents outside groups, duplicate document ids, or missing `source_file_name`/`markdown_file` where previews require them.

3. Add conversion helpers from editable UI shape back to persisted apply shape.
   - Reference: Analysis Section 2, `workflow.py` save responsibilities and Analysis Section 3, apply contract compatibility.
   - Implement `_payload_from_editable_plan(plan: EditableMergePlan) -> dict[str, Any]`.
   - For image groups, emit only `{ "documents": [original image document metadata...] }`.
   - For PDFs, emit the original PDF document metadata as a top-level record.
   - Preserve top-level order exactly as submitted by the browser, including mixed PDF/group order, because `md_mrg.apply.run_apply` processes mixed order correctly.
   - Do not persist UI-only fields: `kind`, `id`, `display_name`, preview URLs, markdown preview URLs, or drag state.

4. Add public `WorkflowService` methods for plan and preview operations.
   - Reference: Analysis Sections 2 and 3, route behavior and security.
   - `get_editable_merge_plan(settings: AppSettings) -> EditableMergePlan`: resolve output dir, load `batch_mrg.json`, convert to editable shape.
   - `save_editable_merge_plan(settings: AppSettings, plan: EditableMergePlan) -> EditableMergePlan`: reject while OCR is running with `409`, validate existing plan exists, atomically write the converted payload to `batch_mrg.json`, and return a freshly loaded editable plan.
   - `resolve_ocr_artifact_preview_path(settings: AppSettings, artifact_id: str) -> Path`: decode an artifact id, require it to stay under output dir, require it to match an editable plan document `source_file_name`, and require the file to exist.
   - `get_markdown_preview(settings: AppSettings, artifact_id: str) -> MarkdownPreviewResponse`: decode/resolve the selected plan document, read its `markdown_file` under output dir, reject traversal, and return UTF-8 content.

5. Update OCR completion flow to fail if the editable plan cannot be loaded.
   - Reference: Analysis Sections 1 and 2, OCR completion exposes plan and malformed plan handling.
   - After `md_mrg_planner.run_plan(...)` and `_update_counts_from_plan(...)`, call the same conversion helper used by `get_editable_merge_plan` before `_mark_complete()`.
   - If conversion fails, mark OCR/planning failed with a useful workflow error and keep Merge unavailable.

**Exit Criterion:** `WorkflowService` can load, validate, convert, save, and resolve artifacts for `batch_mrg.json` while preserving apply-compatible on-disk JSON and output-folder containment.

**Validation Command:** `uv run pytest test/webapp_tests/test_workflow_api.py -q`

## Phase 3: FastAPI Routes and Error Mapping

**Traceability:** Implements Analysis Sections 1, 2 (`src/webapp/backend/app.py`), and 3 (`Error Handling`, `Security & Permissions`).

### Steps

1. In `src/webapp/backend/app.py`, add dedicated merge-plan routes beside existing workflow routes.
   - Reference: Analysis Section 2, `app.py` structural changes.
   - Add `GET /api/workflow/merge-plan -> EditableMergePlan`.
   - Add `PUT /api/workflow/merge-plan -> EditableMergePlan` accepting `EditableMergePlan` and persisting it through `WorkflowService.save_editable_merge_plan(...)`.
   - Load settings inside each route using existing `load_settings(settings_path, defaults_path)`.

2. Add generated artifact preview routes.
   - Reference: Analysis Sections 2 and 3, artifact route and path traversal requirements.
   - Add `GET /api/workflow/ocr-preview/{artifact_id}` returning `FileResponse` for selected OCR output source image/PDF artifacts under output dir.
   - Add `GET /api/workflow/markdown-preview/{artifact_id}` returning `MarkdownPreviewResponse` for the matching generated Markdown file.
   - Keep `/api/workflow/source-preview/{file_id}` unchanged and source-folder scoped.

3. Map errors consistently.
   - Reference: Analysis Section 2, `app.py` logic modifications.
   - Preserve existing `SettingsStoreError -> 500` mapping.
   - Map `WorkflowServiceError.status_code` directly so validation failures return `400`, running-state conflicts return `409`, missing plan/artifacts return `404`, and write failures can return `500`.
   - Use route response typing for normal responses and existing `JSONResponse` fallback pattern for errors.

**Exit Criterion:** Backend API exposes load/save/edit-preview routes with scoped filesystem access and stable HTTP error semantics.

**Validation Command:** `uv run pytest test/webapp_tests/test_workflow_api.py -q`

## Phase 4: Backend and Apply Compatibility Tests

**Traceability:** Implements Analysis Sections 2 (`test/webapp_tests/test_workflow_api.py`, `test/md_mrg/test_mrg_units.py`) and 4 verification checklist.

### Steps

1. Extend `test/webapp_tests/test_workflow_api.py` with helper fixtures for generated output artifacts.
   - Reference: Analysis Section 2, workflow API tests.
   - Create fixture writers for `batch_mrg.json`, image files, PDF files, and Markdown files under the configured output folder.
   - Reuse `_client`, `_write_settings`, and `_encoded_id` patterns already present in the file.

2. Add API tests for plan loading.
   - Reference: Analysis Sections 2 and 4.
   - Verify `GET /api/workflow/merge-plan` returns ordered image groups and standalone PDFs.
   - Verify unknown metadata on documents appears in the editable response.
   - Verify missing and malformed `batch_mrg.json` return explicit error responses.
   - Verify traversal-shaped artifact ids are rejected.

3. Add API tests for plan saving.
   - Reference: Analysis Sections 2, 3, and 4.
   - Verify reordering image pages writes `batch_mrg.json` in the submitted page order.
   - Verify moving a page between existing groups writes the new source and destination groups.
   - Verify a submitted new group writes as a top-level `{ "documents": [...] }` object and omits UI-only fields.
   - Verify empty groups, duplicate page identities, PDFs inside groups, and image pages as top-level items are rejected without changing the existing file.
   - Verify write failure surfaces an error and does not mutate workflow stage state.

4. Add API tests for artifact previews.
   - Reference: Analysis Sections 2, 3, and 4.
   - Verify selected image page preview returns bytes from the output artifact referenced by `source_file_name`.
   - Verify selected PDF plan item preview returns bytes from the output artifact referenced by `source_file_name`.
   - Verify Markdown preview returns generated Markdown content for image and PDF plan items.
   - Verify missing artifacts return `404`.

5. Extend `test/md_mrg/test_mrg_units.py` for edited plan compatibility.
   - Reference: Analysis Sections 2 and 3, apply boundary.
   - Add tests for reordered image pages, singleton groups, multiple groups, and mixed PDF/group order.
   - Add or keep a test proving an empty group fails at apply boundary with `group_image_empty`, supporting the webapp validation rule.

**Exit Criterion:** Backend route tests cover load/save/preview/error paths, and apply tests prove edited plans remain compatible with `md_mrg.apply.run_apply`.

**Validation Command:** `uv run pytest test/webapp_tests/test_workflow_api.py test/md_mrg/test_mrg_units.py -q`

## Phase 5: Frontend Types and API Client

**Traceability:** Implements Analysis Sections 1, 2 (`src/webapp/frontend/src/types.ts`, `src/webapp/frontend/src/api.ts`), and 3 (`State Consistency`).

### Steps

1. Update `src/webapp/frontend/src/types.ts` to mirror backend editable-plan models.
   - Reference: Analysis Section 2, frontend type changes.
   - Add `EditableImagePage`, `EditablePdfDocument`, `EditableImageGroup`, `EditableMergePlan`, `EditablePlanItem`, and `MarkdownPreviewResponse`.
   - Add drag/drop types such as `DragPageState`, `DropTarget`, and variants for `inside-group` and `between-groups`.
   - Replace or retire `OcrTreeRow` and `MergeRow` where placeholder flat rows no longer model the OCR editing stage.
   - Keep `WorkflowSourceFile` and Start-stage discovery types separate from OCR artifact plan types.

2. Update `src/webapp/frontend/src/api.ts` with merge-plan and artifact helpers.
   - Reference: Analysis Section 2, frontend API changes.
   - Add `fetchEditableMergePlan(): Promise<EditableMergePlan>`.
   - Add `saveEditableMergePlan(plan: EditableMergePlan): Promise<EditableMergePlan>` that throws errors in the same style as `startWorkflowOcr`.
   - Add `buildOcrArtifactPreviewUrl(item: EditableImagePage | EditablePdfDocument): string`.
   - Add `fetchMarkdownPreview(item: EditableImagePage | EditablePdfDocument): Promise<MarkdownPreviewResponse>`.
   - Keep `startWorkflowDiscovery`, `startWorkflowOcr`, and `buildSourcePreviewUrl` behavior unchanged.

**Exit Criterion:** Frontend has strongly typed editable-plan data and API helpers, with PDFs modeled as standalone non-draggable items.

**Validation Command:** `Push-Location src/webapp/frontend; npm run build; Pop-Location`

## Phase 6: Frontend Editable OCR Tree and Merge Save Flow

**Traceability:** Implements Analysis Sections 1, 2 (`src/webapp/frontend/src/components/WorkflowPanel.tsx`), and 3 (`UX Boundaries`, `State Consistency`, `Performance / Scale Impact`).

### Steps

1. Replace placeholder OCR rows with editable plan state in `WorkflowPanel.tsx`.
   - Reference: Analysis Sections 1 and 2, workflow panel structural changes.
   - Add state for `editablePlan`, `expandedGroupIds`, `selectedPlanItemId`, `dragState`, `dropTarget`, `dragSnapshot`, `markdownPreview`, and `markdownPreviewStatus`.
   - On initial workflow state load and server-sent OCR completion, fetch the editable plan once with `fetchEditableMergePlan()`.
   - Default loaded image groups to expanded.
   - Do not overwrite an edited plan from generic server-sent state refreshes unless OCR is rerun or Start is rerun.
   - Clear editable plan and OCR selection in `runStart()` and before starting a fresh OCR run.

2. Render image groups, image page rows, and standalone PDFs in the OCR stage.
   - Reference: Analysis Section 2, OCR rendering requirements.
   - Render image groups as expandable parent rows with stable keys and a collapse button.
   - Render image pages as indented selectable child rows with drag handles/`draggable=true`.
   - Render PDF items as selectable standalone rows with no drag handle and no child drop zones.
   - Selection must use stable plan document ids, not group indexes, so moved pages keep preview identity.

3. Implement native drag-and-drop for page movement.
   - Reference: Analysis Sections 2 and 3, UX boundaries.
   - Allow drag start only for `EditableImagePage` rows.
   - On drag start, deep-copy `editablePlan` into `dragSnapshot` for `Esc` cancellation.
   - Allow drop targets inside groups at child insertion indexes.
   - Allow between-group drop targets that create a new `DocumentGroup_N` at the target top-level position.
   - Prevent drops onto PDFs, into PDFs, and from PDFs.
   - On move, remove the page from its source group, insert it at the target, and immediately remove any now-empty source group.
   - On `Esc`, restore `dragSnapshot`, clear active drag/drop state, and leave selection unchanged if possible.

4. Update preview panes for OCR-stage selections.
   - Reference: Analysis Section 2, middle/right preview requirements.
   - Keep Start-stage source preview behavior intact.
   - For OCR selected image pages or PDFs, use `buildOcrArtifactPreviewUrl(...)` in the middle preview panel.
   - For PDF OCR artifacts, reuse the existing `PdfPreview` component.
   - In the right preview panel, load Markdown on selection with `fetchMarkdownPreview(...)`, show loading/error/empty states, and avoid eager loading every row.

5. Update Merge stage click behavior.
   - Reference: Analysis Sections 1, 2, and 4, save-on-Merge behavior.
   - When Merge is clicked, require `editablePlan` to be present.
   - Call `saveEditableMergePlan(editablePlan)` before starting the existing merge simulation timer.
   - If save fails, show the error in the status area, keep `merge` enabled, and do not mark Merge complete or enable Rename.
   - If save succeeds, replace local `editablePlan` with the returned plan and then continue the existing simulated Merge completion flow.

**Exit Criterion:** The OCR stage displays and edits the persisted merge plan, previews selected artifacts/Markdown, supports required drag flows, and saves before Merge completion.

**Validation Command:** `Push-Location src/webapp/frontend; npm run build; Pop-Location`

## Phase 7: Frontend Styling and Documentation

**Traceability:** Implements Analysis Sections 2 (`src/webapp/frontend/src/styles.css`, `src/webapp/README.md`) and 4 frontend verification items.

### Steps

1. Extend `src/webapp/frontend/src/styles.css` for editable OCR tree states.
   - Reference: Analysis Section 2, style requirements.
   - Add classes for group parent rows, child page indentation, PDF standalone rows, selected OCR rows, expand/collapse controls, valid inside-group insertion indicators, between-group insertion indicators, invalid targets, active dragging, and drag-cancel reset.
   - Preserve the existing workflow panel visual language: shell colors, compact rows, bordered scroll list, and stage rail styling.
   - Ensure long filenames and Markdown paths wrap or truncate safely in compact panels.
   - Add focus-visible states for collapse buttons and draggable page rows.

2. Update `src/webapp/README.md`.
   - Reference: Analysis Section 2, documentation requirements.
   - Document the new routes: `GET/PUT /api/workflow/merge-plan`, `GET /api/workflow/ocr-preview/{artifact_id}`, and `GET /api/workflow/markdown-preview/{artifact_id}`.
   - Update scope text to say OCR is wired, editable `batch_mrg.json` loading/saving is implemented, and actual `md_mrg.cli --apply` execution remains out of scope.

**Exit Criterion:** UI states are visually distinct and documented APIs match implemented route behavior.

**Validation Command:** `Push-Location src/webapp/frontend; npm run build; Pop-Location`

## Phase 8: Final Verification Pass

**Traceability:** Implements Analysis Section 4 complete verification checklist.

### Steps

1. Run focused backend and apply tests.
   - Reference: Analysis Section 4, backend and apply verification.
   - Command: `uv run pytest test/webapp_tests/test_workflow_api.py test/md_mrg/test_mrg_units.py -q`.

2. Run focused frontend build/type validation.
   - Reference: Analysis Section 4, frontend type checking and build.
   - Command: `Push-Location src/webapp/frontend; npm run build; Pop-Location`.

3. Optionally run a narrow manual smoke check with backend and frontend dev servers if executable tests pass.
   - Reference: Analysis Section 4, user-facing workflow verification.
   - Start backend with `uv run uvicorn webapp.backend.app:app --reload --port 8000`.
   - Start frontend from `src/webapp/frontend` with `npm run dev`.
   - Verify Start, OCR completion, OCR tree load, page drag/reorder, selection previews, Markdown preview, and Merge save behavior in the browser.

**Exit Criterion:** Focused Python tests pass, frontend production build passes, and any manual smoke check confirms the editable tree and save-on-Merge behavior.

**Validation Command:** `uv run pytest test/webapp_tests/test_workflow_api.py test/md_mrg/test_mrg_units.py -q; Push-Location src/webapp/frontend; npm run build; Pop-Location`