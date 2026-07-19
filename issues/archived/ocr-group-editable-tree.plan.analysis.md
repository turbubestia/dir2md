# Implementation Analysis: ocr-group-editable-tree

## 1. Architectural Impact & Data Flow
*High-level overview of how data flows through the system for this feature. Identify any new patterns or structural additions.*
- **Affected Subsystems:** Frontend workflow UI, frontend workflow API client/types, FastAPI workflow endpoints, backend workflow service state, backend Pydantic models, local filesystem contracts for `batch_mrg.json`, workflow API tests, frontend build/type checks.
- **Data Flow Changes:** OCR generation and merge planning still produce `batch.json` and `batch_mrg.json` in the configured output directory. After planning completes, the backend must read `batch_mrg.json`, normalize it into a webapp-safe editable plan shape, and expose it through workflow state or a dedicated plan endpoint. The frontend must render that plan as an expanded document-group tree, keep an in-memory edited copy while the user drags image pages, resolve selected pages to their original source image and markdown artifacts, and send the edited plan back to the backend when the Merge stage is clicked. The backend must validate and write the edited structure to `batch_mrg.json` before the existing simulated merge behavior proceeds. `md_mrg.cli --apply` remains unwired, but its current input contract remains the compatibility boundary.

## 2. Component & File Impact Map
*Identify the exact files that must be created, modified, or deleted, and what structural changes they require.*

### `./src/webapp/backend/models.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add Pydantic models for editable merge-plan groups, page records, standalone PDF records, and the top-level editable plan returned to the browser.
  - [ ] Represent image groups separately from PDF items so the frontend can distinguish expandable movable groups from non-editable standalone documents.
  - [ ] Preserve original merge-plan document fields needed by `md_mrg.apply.run_apply`, including `source_file_name`, `file_type`, `markdown_file`, `page_count`, `date_of_process`, `summary`, `status`, and any future unknown metadata.
  - [ ] Include UI-facing stable identifiers for groups and page/PDF rows that can be derived from persisted artifact fields without changing the on-disk apply contract.
  - [ ] Extend `WorkflowState` only if the chosen API shape embeds the editable plan in state and server-sent events; otherwise keep the plan behind dedicated endpoints.
- **Logic Modifications Required:**
  - [ ] Validate that only image documents appear as children of editable image groups.
  - [ ] Validate that PDF records remain standalone plan items and are not accepted inside image groups.
  - [ ] Validate that empty image groups are not accepted for persistence because empty groups fail apply-time image merging.
  - [ ] Allow unknown per-document metadata to round-trip so manual UI edits do not discard planner or OCR fields.

### `./src/webapp/backend/workflow.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add workflow-service responsibilities for loading `batch_mrg.json` from the configured output directory after OCR planning completes.
  - [ ] Add workflow-service responsibilities for saving a browser-submitted editable plan back to `batch_mrg.json`.
  - [ ] Add helpers that convert between the on-disk merge-plan shape and the webapp editable-tree shape.
  - [ ] Add preview-path resolution for OCR output artifacts, not only original discovered source files.
  - [ ] Add markdown artifact resolution for page rows so selecting a page can load the matching generated Markdown.
- **Logic Modifications Required:**
  - [ ] When OCR planning reaches completion, read the persisted merge plan and make it available to the UI in the same final state refresh that enables the Merge stage.
  - [ ] Preserve document order exactly as represented by the user-edited tree when saving `batch_mrg.json`.
  - [ ] Delete empty image groups from the editable in-memory representation and persisted payload after a page move removes the final page.
  - [ ] Generate display-only names for new image groups in the `DocumentGroup_N` format while keeping the persisted apply contract focused on `documents` arrays.
  - [ ] Reject save requests if OCR planning has not produced a merge plan yet, if the configured output directory is unavailable, or if the submitted structure would create invalid apply input.
  - [ ] Surface write failures as workflow errors without marking Merge as complete.

### `./src/webapp/backend/app.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add an API route for reading the current editable merge plan if it is not embedded in `WorkflowState`.
  - [ ] Add an API route that persists the edited merge plan when the frontend Merge action is clicked.
  - [ ] Add route(s) for serving generated OCR page image previews and generated Markdown previews by validated artifact identifier.
  - [ ] Add response typing for the new workflow-plan and preview models.
- **Logic Modifications Required:**
  - [ ] Load settings for all filesystem-backed plan and artifact routes so paths resolve against the configured output folder.
  - [ ] Map workflow validation errors to client-meaningful `400` responses, conflict/running-state errors to `409`, missing plan or artifact errors to `404`, and filesystem failures to `500`.
  - [ ] Preserve existing source preview route behavior for the Start stage and avoid broadening it to arbitrary files.

### `./src/webapp/frontend/src/types.ts`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add TypeScript types mirroring the backend editable merge-plan models.
  - [ ] Add discriminated row/item types for image group parents, image page children, and standalone PDF entries.
  - [ ] Add drag state and drop-target shape types for inside-group insertion and between-group insertion.
  - [ ] Add API result types for saving edited merge plans and fetching Markdown preview content.
  - [ ] Update or replace `OcrTreeRow` and `MergeRow` if their current flat placeholder shapes no longer represent OCR group editing.
- **Logic Modifications Required:**
  - [ ] Keep source discovery types separate from OCR plan types so Start-stage source rows and OCR-stage editable rows do not become ambiguous.
  - [ ] Model PDF rows as non-draggable and non-droppable at the type level where practical.

### `./src/webapp/frontend/src/api.ts`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add a client function to fetch or receive the editable OCR merge plan.
  - [ ] Add a client function to persist edited groups before Merge stage simulation proceeds.
  - [ ] Add client helpers for building OCR artifact preview URLs and Markdown preview requests.
- **Logic Modifications Required:**
  - [ ] Convert backend validation and write failures into thrown errors or typed failed results that `WorkflowPanel` can surface in the status area.
  - [ ] Keep existing discovery and OCR start calls unchanged except where they need to refresh the editable plan after OCR completion.

### `./src/webapp/frontend/src/components/WorkflowPanel.tsx`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace the flat `ocrRowsFromWorkflow` output with a tree-shaped state derived from the editable merge plan.
  - [ ] Track expanded/collapsed state per image group, defaulting newly loaded groups to expanded after OCR completes.
  - [ ] Track selected OCR plan row separately from Start-stage selected source rows so selecting a moved page still drives preview panes correctly.
  - [ ] Add drag-and-drop state for image page rows only, including the source group/page, current valid drop target, and cancel state.
  - [ ] Add rendering for image-group parent rows, child image page rows, standalone PDF rows, and between-group insertion targets.
  - [ ] Update the Merge stage click handler so it persists the edited plan before the existing simulated merge completion path runs.
  - [ ] Update the middle preview panel to show selected OCR image pages while retaining existing Start-stage image/PDF preview behavior.
  - [ ] Update the right preview panel to load generated Markdown for the selected OCR page or PDF plan item instead of showing placeholder text.
- **Logic Modifications Required:**
  - [ ] Allow drag starts only from image page child rows.
  - [ ] Allow drops into image groups at specific child insertion indices and between document groups at specific group insertion indices.
  - [ ] Prevent drops onto PDF rows, into PDF rows, or from PDF rows.
  - [ ] Cancel an active drag with `Esc` and restore the original in-memory tree without creating groups or changing page order.
  - [ ] Preserve page artifact references when moving pages within a group, between groups, or into a newly created group.
  - [ ] Delete an image group immediately when its last page is moved away.
  - [ ] Selectable page rows must continue to drive image and Markdown previews after moves because selection is based on the page artifact identity, not its current group position.
  - [ ] Surface save errors in the workflow status area and keep the Merge stage enabled rather than falsely marking it complete.

### `./src/webapp/frontend/src/styles.css`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add styles for expandable group rows, child page indentation, standalone PDF rows, selected OCR rows, valid insertion indicators, invalid drop targets, drag placeholders, and drag-cancel reset states.
  - [ ] Add responsive styles for the editable tree so long filenames and Markdown paths do not overflow compact panels.
  - [ ] Add focus-visible styles for group expand/collapse controls and draggable page rows.
- **Logic Modifications Required:**
  - [ ] Ensure between-group drop targets are visually distinct from inside-group insertion indicators.
  - [ ] Preserve existing workflow visual language for stage rail, panels, and source preview rows.

### `./src/webapp/README.md`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update the documented workflow API list to include editable merge-plan loading, OCR artifact preview, Markdown preview, and save-on-Merge behavior.
  - [ ] Update the deferred-feature section because OCR is now wired and `batch_mrg.json` editing/persistence is no longer fully deferred.
- **Logic Modifications Required:**
  - [ ] Document that the actual `md_mrg.cli --apply` merge execution remains out of scope for this task.

### `./test/webapp_tests/test_workflow_api.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add backend API tests for exposing the persisted `batch_mrg.json` as image groups and standalone PDF entries after OCR completes.
  - [ ] Add backend API tests for saving reordered image pages to `batch_mrg.json`.
  - [ ] Add backend API tests for saving a page moved between groups and a page moved into a newly created group.
  - [ ] Add backend API tests for rejecting PDF participation in page movement and rejecting empty groups.
  - [ ] Add backend API tests for generated image and Markdown preview artifact resolution.
- **Logic Modifications Required:**
  - [ ] Verify save failures and missing plan errors return explicit error responses and do not silently change workflow stage state.
  - [ ] Verify unknown document metadata round-trips through load and save.

### `./test/md_mrg/test_mrg_units.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add or extend apply-stage compatibility tests using manually edited `batch_mrg.json` structures containing reordered image pages, singleton groups, multiple groups, and PDF passthrough records.
- **Logic Modifications Required:**
  - [ ] Verify `md_mrg.apply.run_apply` continues to merge group Markdown and images in the edited order.
  - [ ] Verify empty image groups remain invalid at the apply boundary, supporting the webapp rule that they must be deleted before persistence.

### `./src/webapp/frontend/package.json`
- **Type of Change:** Modify if needed
- **Structural Changes:**
  - [ ] Add a drag-and-drop dependency only if native browser drag events cannot satisfy keyboard cancel, insertion indicators, and nested tree behavior with acceptable complexity.
- **Logic Modifications Required:**
  - [ ] Keep dependency choice consistent with React 18 and Vite; no dependency is required if the implementation uses native drag-and-drop.

## 3. Boundary & Edge Case Analysis
*Detail how system boundaries, errors, and edge cases will be handled structurally.*
- **Error Handling:** Missing `batch_mrg.json` after OCR completion should remain an OCR/planning failure because the tree cannot be built. Loading a malformed plan should surface a workflow error and keep Merge unavailable or failed. Saving an edited plan should fail fast if the payload contains PDFs inside groups, image pages outside groups, empty groups, duplicate page identities, missing required artifact fields, or invalid top-level `documents`. Filesystem write errors should return an error response and prevent the frontend from marking Merge complete. Missing preview artifacts should return `404` without crashing the workflow panel.
- **Security & Permissions:** All plan, image preview, and Markdown preview routes must resolve paths under the configured output directory and reject path traversal or absolute-path escape attempts. The API should not accept arbitrary client-provided filesystem paths for preview or persistence. There is no new authentication or RBAC layer in the local webapp, but the local filesystem boundary must remain explicit.
- **Performance / Scale Impact:** The editable plan is a small JSON document relative to OCR artifacts; loading and saving it on OCR completion and Merge click should be cheap. Frontend drag operations should update in-memory arrays without rereading files. Markdown preview loading should be on selection, not eagerly for every page. Very large image batches need stable row keys and minimal tree rerendering to keep drag feedback responsive.
- **Data Contract Compatibility:** The saved `batch_mrg.json` must keep the top-level `documents` array. Image groups must remain objects with a `documents` array containing original image document records. PDF entries must remain standalone document records. The current docs say image groups come before PDFs, but the new requirement allows creating a group between document groups; implementation planning must decide whether preserving current planner ordering is mandatory for compatibility or whether `run_apply`'s actual ability to process mixed group/PDF order is the controlling contract. This analysis treats `run_apply` compatibility as the hard boundary and identifies any ordering-policy decision as an implementation-plan item.
- **UX Boundaries:** Drag-and-drop is the only page movement mechanism. Group expand/collapse changes only UI state and must never mutate the persisted plan. `Esc` cancels the active drag and must leave the pre-drag tree unchanged. PDF rows must not expose drag handles, child drop zones, or page-level editing affordances. Between-group targets must look different from inside-group targets to reduce accidental new group creation.
- **State Consistency:** The frontend should keep one authoritative edited plan after OCR completion. Server-sent workflow state can announce stage/progress changes, but client-side edits should not be overwritten by a routine state refresh unless OCR is rerun or the plan is explicitly reloaded. Rerunning Start or OCR should clear edited plan state and selection because a new source/output set invalidates previous row identities.

## 4. Verification Checklist
*A concrete list of what needs to be verified during/after implementation to ensure the analysis was correct.*
- [ ] Verify OCR completion exposes `batch_mrg.json` image groups as expanded tree parents with ordered image page children.
- [ ] Verify PDF records display as single non-draggable rows with no child rows or drop targets.
- [ ] Verify group expand/collapse hides and shows children without changing the saved plan.
- [ ] Verify selecting an image page child loads its image preview from the original artifact and loads its generated Markdown content.
- [ ] Verify selecting a moved or reordered image page still resolves the same image and Markdown artifacts.
- [ ] Verify dragging a page within the same group updates only that group's page order.
- [ ] Verify dragging a page into another image group removes it from the source group and inserts it at the indicated target position.
- [ ] Verify dragging a page between groups creates a new `DocumentGroup_N` group at that position.
- [ ] Verify moving the final page out of an image group deletes the empty source group immediately.
- [ ] Verify `Esc` during an active drag cancels the operation and restores the original grouping and ordering.
- [ ] Verify pages cannot be dropped onto or inside PDF records and PDF records cannot be dragged as pages.
- [ ] Verify clicking Merge writes the edited structure to `batch_mrg.json` before the Merge stage is marked complete or any later merge behavior could consume it.
- [ ] Verify write failures surface an error and do not mark Merge complete.
- [ ] Verify saving without edits leaves `batch_mrg.json` semantically equivalent to the existing plan.
- [ ] Verify saved edited plans remain consumable by `md_mrg.apply.run_apply` for reordered groups, moved pages, singleton groups, and PDF passthrough records.
- [ ] Verify backend route tests cover malformed plan files, invalid submitted structures, missing artifacts, traversal attempts, and metadata round-tripping.
- [ ] Verify frontend type checking and build pass after the workflow tree, preview, and API type changes.
- [ ] Verify the focused Python webapp tests pass under `uv run pytest test/webapp_tests/test_workflow_api.py`.
---