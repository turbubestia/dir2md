# Implementation Analysis: wire-merge-documents-sub2

## 1. Architectural Impact & Data Flow
*High-level overview of how data flows through the system for this feature. Identify any new patterns or structural additions.*
- **Affected Subsystems:** Webapp frontend workflow panel, webapp API routes, webapp workflow background worker/state service, shared webapp Pydantic/TypeScript contracts, `md_mrg` apply pipeline, merge-result preview serving, workflow API tests, merge apply tests, frontend workflow tests or type checks, and `md_mrg` developer documentation.
- **Data Flow Changes:** User completes OCR/planning -> frontend loads editable OCR merge plan from `batch_mrg.json` -> user edits group order/membership in memory -> user clicks `Merge` -> frontend sends the current editable plan with the merge-start request -> backend validates and atomically rewrites `batch_mrg.json` -> backend starts a merge apply background worker using the same in-process module invocation pattern as OCR generation and merge planning -> worker calls `md_mrg.apply.run_apply` against the OCR output folder and emits group-level progress -> workflow state broadcasts `merge_status`, merge progress, and per-group statuses through the existing SSE channel -> frontend keeps the group list visible and disabled while merge runs -> when apply finishes and `batch_mrg_result.json` is readable, backend exposes merge result items -> frontend switches the Merge stage from group progress to PDF/Markdown result previews.
- **Existing Pattern Reuse:** The feature should extend `WorkflowService` rather than introduce a separate job manager. The existing `_worker`, lock, `WorkflowState`, `WorkflowProgress`, status messages, and `/api/workflow/events` SSE channel already provide the required non-blocking execution and polling/streaming model for OCR and planning.
- **New Structural Pattern:** The workflow state needs distinct OCR/planning lifecycle state and merge lifecycle state. OCR completion should enable merge, but merge execution must own `WorkflowProgress(stage="merge")`, active group status, and terminal result/error visibility independently of `ocr_status`.
- **Apply Boundary Shift:** PDF copy behavior belongs in `md_mrg.apply` and must be triggered by the webapp only through the apply pipeline. The webapp backend/frontend should not add a separate PDF copy or overwrite-collision path.

## 2. Component & File Impact Map
*Identify the exact files that must be created, modified, or deleted, and what structural changes they require.*

### `./src/md_mrg/apply.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add apply-stage progress event types and an optional progress callback accepted by `run_apply`, parallel to `md_mrg.planner.PlanningProgressEvent`.
  - [ ] Emit group/work-item lifecycle events for apply start, item start, item complete, item failed, result persisted, complete, and fatal failure.
  - [ ] Preserve the current `batch_mrg.json` input and `batch_mrg_result.json` output contract while making result payload fields sufficient for merge result previews: item identity/order, item type, status, output PDF, output Markdown, summary, source document(s), and failure metadata where applicable.
  - [ ] Add a copy responsibility for source PDF files so a PDF referenced by a merge plan can be copied from the original configured source folder into the apply output folder while leaving the original source file in place.
  - [ ] Keep overwrite/collision behavior inside apply, using `cfg.runtime.overwrite` as the source of truth for replacing existing output PDFs/Markdown/result files.
- **Logic Modifications Required:**
  - [ ] Treat `cfg.paths.source_dir` as the original source folder when resolving source PDFs that are not already present in the apply/output folder.
  - [ ] Treat the `source_dir` argument passed to `run_apply` as the reviewed OCR output/apply working folder containing `batch_mrg.json`, OCR Markdown, image artifacts, and `batch_mrg_result.json`.
  - [ ] Copy, not move, each source PDF used by a successful PDF item into the apply output folder according to apply's existing filename and overwrite rules.
  - [ ] Emit progress only at top-level merge item/group granularity, not per child page.
  - [ ] Continue recording failed group items in `batch_mrg_result.json` and continuing later groups where the current apply contract already supports it.
  - [ ] Surface fatal apply errors, including unreadable plan/result files and invalid top-level plan shape, through `ApplyError` so the webapp can mark merge terminal failure without pretending results loaded successfully.

### `./src/md_mrg/cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Keep `--apply` dispatch mapped to `run_apply` and compatible with the new optional progress callback default.
  - [ ] Preserve existing CLI behavior and exit codes for direct terminal use.
- **Logic Modifications Required:**
  - [ ] Ensure direct `md-mrg --apply` runs still receive the same path semantics needed for PDF copy behavior through `build_md_mrg_config_from_args`.
  - [ ] Avoid webapp-specific branching in CLI code; any new apply behavior should be part of the reusable apply module.

### `./src/common/config.py`
- **Type of Change:** Modify / Verify
- **Structural Changes:**
  - [ ] Verify whether `build_md_mrg_config_from_args` can represent both the original PDF source folder and the apply working/output folder. If not, the config boundary must be adjusted without breaking md_gen or existing md_mrg plan/apply callers.
  - [ ] Keep `runtime.overwrite` as the shared overwrite flag used by apply.
- **Logic Modifications Required:**
  - [ ] Ensure `md_mrg` apply has enough path information to copy PDFs from the source folder to the output folder while direct CLI and webapp invocations remain consistent.

### `./src/webapp/backend/models.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Extend `WorkflowProgress.stage` to include `merge`.
  - [ ] Add merge lifecycle status to `WorkflowState`, likely parallel to `ocr_status`, with values compatible with `WorkflowStageStatus`.
  - [ ] Add group-level merge progress state to `WorkflowState`, including pending, running, done, and failed statuses keyed by stable top-level editable plan/group identifiers.
  - [ ] Add active merge item/group identity to `WorkflowState` so the frontend can highlight the running group.
  - [ ] Add merge result response models for successful and failed `batch_mrg_result.json` items, with PDF/Markdown preview references and failure metadata.
  - [ ] Add request model for starting merge that carries the current `EditableMergePlan` payload so unsaved frontend edits are persisted before apply begins.
- **Logic Modifications Required:**
  - [ ] Preserve existing OCR state fields for compatibility while allowing merge state to advance independently after OCR has completed.
  - [ ] Keep editable plan models permissive enough to round-trip extra document metadata required by `batch_mrg.json`.

### `./src/webapp/backend/workflow.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Import and use `md_mrg.apply` alongside the existing `md_mrg.planner` integration.
  - [ ] Add a public `start_merge(settings, plan)` workflow service method that validates current state, prevents duplicate merge jobs, persists the provided editable plan to `batch_mrg.json`, initializes merge state, and starts a background worker.
  - [ ] Add a merge worker method that builds runtime config from settings, invokes apply with the OCR output folder as the apply working directory, handles apply progress callbacks, loads `batch_mrg_result.json`, and marks merge complete or failed.
  - [ ] Add helper boundaries for loading/validating merge result payloads and converting them to webapp result models.
  - [ ] Add preview path resolution helpers for merge result PDFs and Markdown files, distinct from OCR preview helpers.
  - [ ] Update save/editable-plan guard rails so plan saving and merge start are rejected while OCR or merge is running, except for the atomic rewrite performed as part of merge start.
- **Logic Modifications Required:**
  - [ ] Reject merge start when OCR/planning has not completed, `batch_mrg.json` is missing or malformed, or another workflow worker is running.
  - [ ] Rewrite `batch_mrg.json` from the supplied editable plan before invoking apply, using the existing `_payload_from_editable_plan` and `_write_json_atomic` boundaries.
  - [ ] If rewriting `batch_mrg.json` fails, do not start apply and return an actionable API error.
  - [ ] Initialize all top-level editable plan items/groups to pending merge status at merge start.
  - [ ] Mark the active top-level group/item running when apply progress identifies it, then done or failed as progress/result metadata indicates.
  - [ ] Keep the UI on group progress state until apply has completed and result loading has succeeded or failed explicitly.
  - [ ] On successful apply completion, load `batch_mrg_result.json`; if missing or malformed, mark merge terminal failure with an error state rather than an empty successful result list.
  - [ ] Allow flow advancement to merge results when `batch_mrg_result.json` contains failed item metadata, preserving failed group labels for display.
  - [ ] Continue broadcasting every meaningful state update through `_broadcast` and the existing SSE subscription mechanism.

### `./src/webapp/backend/app.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add a `POST /api/workflow/merge` route that accepts the current editable plan and returns `WorkflowState` after merge start initialization.
  - [ ] Add a `GET /api/workflow/merge-results` route for loading final result items from `batch_mrg_result.json` after apply completion.
  - [ ] Add merge result PDF and Markdown preview routes or extend existing preview routes with result-aware resolution.
  - [ ] Reuse existing settings loading, Pydantic validation, `WorkflowServiceError`, and JSON error response patterns.
- **Logic Modifications Required:**
  - [ ] Return `409 Conflict` for duplicate merge start while a merge or other workflow job is running.
  - [ ] Return `400`/`404` style workflow errors for invalid state, missing plan/result files, invalid payloads, and missing preview artifacts.
  - [ ] Avoid exposing arbitrary filesystem paths through preview routes; use encoded IDs or backend-validated relative result paths.

### `./src/webapp/frontend/src/types.ts`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Mirror backend workflow contract changes: `WorkflowProgress.stage` includes `merge`, `WorkflowState` includes merge status, active merge item/group, merge item statuses, and merge result availability/error state.
  - [ ] Replace placeholder `MergeRow` status shape with real merge progress/result types.
  - [ ] Add merge result item types for PDF and group outputs, including `ok` and `failed` statuses, output PDF, output Markdown, summary, source document(s), error code, and message.
- **Logic Modifications Required:**
  - [ ] Keep OCR editable plan document/group types compatible with the payload sent to merge start.
  - [ ] Represent merge previews as PDF plus Markdown only; do not carry image preview alternatives into merge result types.

### `./src/webapp/frontend/src/api.ts`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add `startWorkflowMerge(plan)` API client that posts the current `EditableMergePlan` to the backend merge route.
  - [ ] Add `fetchMergeResults()` API client for final result loading.
  - [ ] Add URL builders or fetch helpers for merge result PDF and Markdown previews.
  - [ ] Keep existing editable merge plan load/save helpers for OCR-stage editing where still useful.
- **Logic Modifications Required:**
  - [ ] Stop modeling merge start as save-plan followed by frontend simulation.
  - [ ] Surface backend merge start, result load, and preview errors through the same error-message style as existing OCR helpers.

### `./src/webapp/frontend/src/components/WorkflowPanel.tsx`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace `runSimulatedStage('merge')` usage in `runMergeStage` with real merge API start.
  - [ ] Keep the existing editable OCR tree as the merge progress list while merge is running.
  - [ ] Add group-level status rendering for pending, running, done, and failed on top-level editable plan groups/items during merge.
  - [ ] Add merge-result list rendering after merge completes and results are loaded from `batch_mrg_result.json`.
  - [ ] Add result selection state that is distinct from OCR plan item selection if needed for PDF/Markdown result previews.
  - [ ] Update middle/right preview panels so the Merge stage shows result PDFs and generated Markdown only after result data is available.
  - [ ] Update stage-state derivation so active progress belongs to `merge` while merge runs and OCR no longer owns the active progress indicator after OCR completion.
  - [ ] Reuse the existing stage-running disabled/ignored interaction behavior for merge, including button disablement, row click suppression, drag/drop suppression, and panel mouse-event blocking.
- **Logic Modifications Required:**
  - [ ] Send the in-memory `editablePlan` directly with the merge start request so stale on-disk groups are not used.
  - [ ] Keep selected stage on Merge during merge progress and avoid switching to result rows until backend state indicates apply completion and result loading is available.
  - [ ] Mark failed groups red when progress or final result metadata reports failed item status.
  - [ ] Enable Rename only after merge reaches the appropriate terminal state and result data has been handled.
  - [ ] Preserve OCR-stage image/PDF preview behavior, but do not show image previews for Merge result items.

### `./src/webapp/frontend/src/App.css` or related workflow stylesheet
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add or extend row status classes for merge pending, running, done, and failed states.
  - [ ] Add styling for merge result rows and failure labels while matching the existing workflow panel visual language.
  - [ ] Ensure disabled/ignored interaction styling during merge matches OCR-running behavior.
- **Logic Modifications Required:**
  - [ ] Keep status colors consistent with current OCR status semantics: done green, failed red, pending neutral, running highlighted.

### `./docs/internals/md_mrg.md`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update apply-flow documentation to describe PDF copy behavior, current output names, result payload fields, and failed group semantics.
  - [ ] Clarify that copy/overwrite behavior is owned by `md_mrg --apply`.
- **Logic Modifications Required:**
  - [ ] Remove or correct stale statements that describe standalone PDFs only as passthrough status items when apply now produces/copies final artifacts for preview.

### `./test/webapp_tests/test_workflow_api.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add backend API tests for merge start validation, duplicate job conflict, atomic plan rewrite from payload, merge worker progress updates, result loading, missing/malformed result errors, and merge preview path safety.
  - [ ] Extend existing workflow state tests for `merge_status`, `progress.stage == "merge"`, active merge item/group, and group status lists.
- **Logic Modifications Required:**
  - [ ] Monkeypatch `webapp.backend.workflow.md_mrg_apply.run_apply` or equivalent to make merge worker behavior deterministic.
  - [ ] Verify invalid editable plan payloads do not mutate existing `batch_mrg.json` and do not start apply.
  - [ ] Verify failed result metadata advances to result display state while preserving failed group visibility.

### `./test/md_mrg/test_mrg_units.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add tests for apply progress callback event order and item/group status metadata.
  - [ ] Add tests proving source PDFs are copied into the output/apply folder and remain in the original source folder.
  - [ ] Add tests for overwrite-enabled PDF copy replacement and overwrite-disabled collision behavior if applicable to the apply contract.
  - [ ] Update existing tests that assume PDFs already exist only in the apply working folder where the new source/output distinction changes expectations.
- **Logic Modifications Required:**
  - [ ] Keep existing group failure continuation tests intact while adding progress/result assertions.

### `./test/md_mrg/test_mrg_plan.py`
- **Type of Change:** Modify / Verify
- **Structural Changes:**
  - [ ] Verify CLI/config path behavior still supports direct `--apply` usage after PDF copy path semantics are clarified.
  - [ ] Preserve existing planner tests unless shared config changes require fixture updates.
- **Logic Modifications Required:**
  - [ ] Ensure apply invocation through CLI does not regress `--plan` behavior or existing error return codes.

### `./src/webapp/frontend` test/typecheck surface
- **Type of Change:** Modify / Verify
- **Structural Changes:**
  - [ ] Add or update frontend tests where available for merge API calls, merge-running disabled interaction, group status rendering, result list switching, and PDF/Markdown-only preview behavior.
  - [ ] Update TypeScript type checks for expanded workflow and merge result contracts.
- **Logic Modifications Required:**
  - [ ] Verify the UI does not keep showing placeholder merge rows once real backend results are available.

## 3. Boundary & Edge Case Analysis
*Detail how system boundaries, errors, and edge cases will be handled structurally.*
- **Error Handling:** Merge start should fail before starting a worker if OCR has not completed, `batch_mrg.json` is missing, the editable plan payload is invalid, the atomic rewrite fails, or another workflow job is running. The API should preserve current `WorkflowServiceError` response conventions with actionable messages and appropriate `400`, `404`, `409`, or `500` status codes.
- **Worker Failure Boundary:** Fatal `ApplyError` conditions should mark merge as failed and keep the frontend in an inspectable state. Group-scoped apply failures recorded in `batch_mrg_result.json` are not the same as fatal worker failure; those should allow the process to advance to merge results while rendering failed group labels.
- **Result Loading Boundary:** `batch_mrg_result.json` is authoritative only after apply completion. If it is missing, unreadable, malformed, or lacks an `items` list after completion, the backend should expose an error state rather than returning an empty successful result set.
- **Editable Plan Boundary:** The frontend in-memory `EditableMergePlan` must be the source of truth at merge start. The backend must validate and persist this payload before apply reads it, so stale on-disk `batch_mrg.json` data is not used.
- **Progress Granularity:** Merge progress is group/top-level item only. Child image pages should not receive separate merge statuses even if apply internals process them individually.
- **Stage State Boundary:** OCR/planning completion enables Merge. Merge running must set `WorkflowProgress.stage` to `merge`, disable workflow panel interaction, and prevent OCR from appearing as the active progress owner. Merge completion or terminal failure must restore allowed interactions according to stage availability.
- **Preview Boundary:** OCR previews resolve source images/PDFs and OCR Markdown from editable plan records. Merge result previews must resolve only final PDFs and final Markdown files from `batch_mrg_result.json`; image-specific preview controls and fallbacks are out of scope for merge results.
- **Filesystem Safety:** Preview and artifact resolution must continue rejecting absolute paths, `..` traversal, missing files, directories, and unsupported source references. Merge result payloads must not be trusted as arbitrary filesystem paths without backend normalization against the configured output/apply directory.
- **PDF Copy Ownership:** The backend and frontend should rely on `md_mrg.apply` for copying source PDFs and handling overwrite behavior. They should not duplicate copy logic, collision checks, or cleanup behavior outside the apply module.
- **Concurrency:** The existing single `_worker` field means merge and OCR should be mutually exclusive. The service must avoid races where a merge start overwrites state while OCR/planning is still running or a previous merge worker is active.
- **Performance / Scale Impact:** Merge apply remains linear in top-level plan items plus image pages. SSE state broadcasts should send compact status data rather than entire large Markdown contents. File copy cost for PDFs is bounded by PDF size and should happen in the background worker, not the request thread.
- **Security & Permissions:** No new authentication or RBAC is introduced. All filesystem access remains local and constrained to configured source/output folders. Existing CORS and settings-loading behavior remain unchanged.

## 4. Verification Checklist
*A concrete list of what needs to be verified during/after implementation to ensure the analysis was correct.*
- [ ] Verify `POST /api/workflow/merge` rejects requests before OCR/planning completion.
- [ ] Verify `POST /api/workflow/merge` rejects duplicate merge starts while merge is running.
- [ ] Verify merge start rewrites `batch_mrg.json` from the posted editable plan before `run_apply` is invoked.
- [ ] Verify invalid editable plan payloads do not mutate `batch_mrg.json` and do not start apply.
- [ ] Verify workflow state reports `merge_status == "running"` and `progress.stage == "merge"` during apply.
- [ ] Verify all top-level editable groups/items start as pending when merge begins.
- [ ] Verify apply progress marks one top-level group/item running and then done or failed.
- [ ] Verify the frontend progress bar is associated with the Merge stage while merge is running.
- [ ] Verify OCR no longer owns the active progress indicator after OCR completion and merge start.
- [ ] Verify workflow panel mouse interaction, row selection, and drag/drop are disabled or ignored while merge is running.
- [ ] Verify the UI keeps the group progress list visible while merge is incomplete, even if partial output files exist.
- [ ] Verify successful apply completion loads `batch_mrg_result.json` and switches the Merge stage to final result rows.
- [ ] Verify missing or malformed `batch_mrg_result.json` after apply completion displays an error instead of an empty successful result list.
- [ ] Verify failed item metadata in `batch_mrg_result.json` advances to result display and renders failed labels in red.
- [ ] Verify merge result preview offers final PDF and Markdown only, with no image preview controls or fallbacks.
- [ ] Verify merge preview routes reject traversal, absolute paths, missing files, and malformed result IDs.
- [ ] Verify source PDFs are copied into the output/apply folder by `md_mrg.apply` and remain in the original source folder.
- [ ] Verify PDF overwrite/collision behavior is governed by `md_mrg.apply` and `cfg.runtime.overwrite`, not by webapp-specific copy logic.
- [ ] Verify direct `md-mrg --apply` behavior remains compatible with the updated apply path/copy semantics.
- [ ] Verify existing OCR discovery, OCR execution, merge-plan load/save, OCR preview, and markdown preview tests still pass.
- [ ] Run focused backend tests with `uv run pytest test/webapp_tests/test_workflow_api.py`.
- [ ] Run focused merge apply tests with `uv run pytest test/md_mrg`.
- [ ] Run frontend type checks/tests for the webapp workflow after TypeScript contract updates.
