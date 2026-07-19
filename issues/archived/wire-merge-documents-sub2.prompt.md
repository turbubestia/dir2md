# Implementation Plan: wire-merge-documents-sub2

> **Core Objective:** Detailed step-by-step technical execution blueprint for implementing the requirements specified in the analysis.

> **Analysis Reference:** [Analysis Reference](./wire-merge-documents-sub2.plan.analysis.md)  
> **Traceability Scope:** Every phase and step below cites the source analysis section that justifies it. The coding phase must modify implementation files only after following this plan.

## Implementation Guardrails
- Implement only the merge-apply wiring described here. Do not refactor unrelated OCR, settings, or planner behavior. *(Analysis Sections 1, 2, 3)*
- Preserve the current single-process `WorkflowService` worker/SSE model; do not introduce a second job manager, task queue, or frontend-only simulation path for merge. *(Analysis Section 1)*
- Keep source PDF copy, overwrite, collision, and failed-group result semantics inside `src/md_mrg/apply.py`; the webapp must only invoke apply and preview validated outputs. *(Analysis Sections 1, 2, 3)*
- Use `uv run pytest ...` for Python validation and `npm run build` from `src/webapp/frontend` for frontend validation. *(Analysis Section 4)*

## Phase 1: Extend `md_mrg.apply` as the Apply Owner
**Traceability:** Implements Analysis Section 2 `./src/md_mrg/apply.py`, Section 2 `./src/md_mrg/cli.py`, Section 2 `./src/common/config.py`, Section 3 PDF Copy Ownership, Worker Failure Boundary, Progress Granularity, and Filesystem Safety.

### Steps
- **Step 1.1 - Add apply progress contract.** *(Analysis Section 2 `./src/md_mrg/apply.py`)*  
  Add a typed progress event in `src/md_mrg/apply.py`, parallel to `md_mrg.planner.PlanningProgressEvent`, without changing direct CLI behavior. Use a concise local contract such as:
  ```python
  ApplyProgressKind = Literal[
      "stage_start", "item_start", "item_complete", "item_failed",
      "result_persisted", "complete", "failed",
  ]

  @dataclass(frozen=True)
  class ApplyProgressEvent:
      kind: ApplyProgressKind
      item_index: int | None = None
      item_id: str | None = None
      item_type: str | None = None
      status: str | None = None
      total_items: int = 0
      completed_items: int = 0
      output_pdf: str | None = None
      output_markdown: str | None = None
      error_code: str | None = None
      message: str | None = None
  ```
  Update `run_apply` to accept `progress_callback: Callable[[ApplyProgressEvent], None] | None = None` and call it through a helper that does not convert callback failures into successful apply results.

- **Step 1.2 - Make PDF source resolution explicit.** *(Analysis Section 2 `./src/md_mrg/apply.py`; Section 3 PDF Copy Ownership)*  
  Treat the `source_dir` argument to `run_apply(source_dir, cfg, ...)` as the apply working/output folder containing `batch_mrg.json`, OCR Markdown, images, and `batch_mrg_result.json`. Treat `cfg.paths.source_dir` as the original source folder for source PDFs. For PDF items, resolve the source PDF by checking the apply folder first for backward compatibility, then `cfg.paths.source_dir / source_file_name`; copy the source PDF into the apply folder using the planned output PDF name. Never move or delete the original PDF.

- **Step 1.3 - Preserve and enrich result payloads.** *(Analysis Section 2 `./src/md_mrg/apply.py`; Section 3 Result Loading Boundary)*  
  Keep `batch_mrg.json` as input and `batch_mrg_result.json` as output with top-level `{"items": [...]}`. Ensure each successful PDF/group item includes `item_index`, `item_type`, `status: "ok"`, `output_pdf`, `output_markdown`, `summary`, and either `document` or `documents`. Ensure failed group items include `item_index`, `item_type: "group"`, `status: "failed"`, `error_code`, `message`, and `documents`. Do not let failed group items abort later groups unless the existing contract already treats the error as fatal.

- **Step 1.4 - Apply overwrite/collision consistently.** *(Analysis Section 2 `./src/md_mrg/apply.py`; Section 3 PDF Copy Ownership)*  
  Use `cfg.runtime.overwrite` for result file, copied PDF, and Markdown output collisions. Keep `_ensure_can_write` as the central collision guard; allow the PDF copy source and destination to be the same resolved file for direct CLI/backward-compatible cases.

- **Step 1.5 - Emit top-level progress only.** *(Analysis Section 2 `./src/md_mrg/apply.py`; Section 3 Progress Granularity)*  
  Emit `stage_start` once with total top-level plan items. Emit `item_start`, `item_complete`, or `item_failed` once per top-level PDF/group item. Emit `result_persisted` after `batch_mrg_result.json` is written, then `complete`. Emit `failed` before raising fatal `ApplyError` for missing plan, invalid plan shape, unreadable JSON, result write failure, or output collision outside recoverable group failures.

- **Step 1.6 - Verify config/CLI compatibility.** *(Analysis Section 2 `./src/md_mrg/cli.py`; Section 2 `./src/common/config.py`)*  
  Keep `src/md_mrg/cli.py` dispatch as `run_apply(source_dir=config.paths.source_dir, cfg=config)` with the callback omitted. Verify whether `build_md_mrg_config_from_args` needs an output/apply folder distinction. If a config change is required, preserve current `md-mrg --plan` behavior and avoid webapp-specific branches in CLI code.

**Exit Criterion:** `run_apply` supports deterministic progress callbacks, source PDF copy from original source to apply output, enriched result payloads, and unchanged direct CLI invocation semantics.

**Validation Command:** `uv run pytest test/md_mrg/test_mrg_units.py test/md_mrg/test_mrg_plan.py`

## Phase 2: Extend Backend Models and Workflow State
**Traceability:** Implements Analysis Section 2 `./src/webapp/backend/models.py`, Section 3 Stage State Boundary, Editable Plan Boundary, Result Loading Boundary, and Concurrency.

### Steps
- **Step 2.1 - Expand workflow progress/stage state.** *(Analysis Section 2 `./src/webapp/backend/models.py`; Section 3 Stage State Boundary)*  
  In `src/webapp/backend/models.py`, extend `WorkflowProgress.stage` to include `"merge"`. Add `merge_status: WorkflowStageStatus = "idle"` to `WorkflowState` while preserving existing `ocr_status` semantics.

- **Step 2.2 - Add group-level merge progress models.** *(Analysis Section 2 `./src/webapp/backend/models.py`; Section 3 Progress Granularity)*  
  Add a merge item status literal such as `Literal["pending", "running", "done", "failed"]` and a compact model containing stable top-level plan id, label, item type, item index, status, optional output PDF/Markdown, and optional error message/code. Add `active_merge_item_id: str | None`, `merge_items: list[...]`, `merge_results_available: bool`, and `merge_result_error: WorkflowStatusMessage | None` to `WorkflowState`.

- **Step 2.3 - Add merge request/result response models.** *(Analysis Section 2 `./src/webapp/backend/models.py`; Section 3 Preview Boundary)*  
  Add a request model that carries the current `EditableMergePlan`, for example `WorkflowMergeRequest(plan: EditableMergePlan)`. Add result models for `batch_mrg_result.json` items with `id`, `item_index`, `item_type`, `status`, `label`, `output_pdf`, `output_markdown`, `summary`, `document` or `documents`, and optional `error_code`/`message`. Reuse permissive document models so extra `batch_mrg.json` metadata round-trips.

**Exit Criterion:** Backend Pydantic models represent merge lifecycle, group progress, start request payload, result availability/errors, and final result rows without breaking existing OCR state fields.

**Validation Command:** `uv run pytest test/webapp_tests/test_workflow_api.py -q`

## Phase 3: Wire Backend Merge Service and Routes
**Traceability:** Implements Analysis Section 2 `./src/webapp/backend/workflow.py`, Section 2 `./src/webapp/backend/app.py`, and Section 3 Error Handling, Worker Failure Boundary, Result Loading Boundary, Editable Plan Boundary, Filesystem Safety, and Concurrency.

### Steps
- **Step 3.1 - Import apply through a monkeypatchable boundary.** *(Analysis Section 2 `./src/webapp/backend/workflow.py`; Section 4 backend tests)*  
  In `src/webapp/backend/workflow.py`, import `md_mrg.apply` as a module, e.g. `from md_mrg import apply as md_mrg_apply`, and import `ApplyError`/`ApplyProgressEvent` only if needed for typing. Tests should be able to monkeypatch `webapp.backend.workflow.md_mrg_apply.run_apply`.

- **Step 3.2 - Add merge-start validation and atomic plan rewrite.** *(Analysis Section 2 `./src/webapp/backend/workflow.py`; Section 3 Editable Plan Boundary, Concurrency)*  
  Add `WorkflowService.start_merge(settings: AppSettings, plan: EditableMergePlan) -> WorkflowState`. Under the service lock, reject if `_worker` is alive, `ocr_status != "complete"`, or `merge_status == "running"`. Resolve output dir, require existing `batch_mrg.json`, validate the submitted `EditableMergePlan`, convert it using `_payload_from_editable_plan`, and write it with `_write_json_atomic` before starting the worker. If validation or write fails, return a `WorkflowServiceError` and do not start apply.

- **Step 3.3 - Initialize merge state from top-level editable plan items.** *(Analysis Section 2 `./src/webapp/backend/workflow.py`; Section 3 Progress Granularity)*  
  Build `WorkflowState.merge_items` from `plan.items` before starting the worker. Use stable ids from `EditableImageGroup.id` and `EditablePdfDocument.id`; labels should use group `display_name` or PDF `source_file_name`; item indexes must match top-level plan order. Set `merge_status="running"`, `progress=WorkflowProgress(stage="merge", total_jobs=len(items), completed_jobs=0, percent=0.0)`, `active_merge_item_id=None`, `merge_results_available=False`, and clear merge result errors.

- **Step 3.4 - Implement the merge worker.** *(Analysis Section 2 `./src/webapp/backend/workflow.py`; Section 3 Worker Failure Boundary)*  
  Add a private worker method that builds runtime config from settings, but invokes apply with the OCR output/apply directory: `md_mrg_apply.run_apply(source_dir=output_dir, cfg=config, progress_callback=self._handle_apply_progress)`. Ensure `config.paths.source_dir` still points to the original source folder so apply can copy PDFs. Catch `md_mrg_apply.ApplyError` and mark merge as terminal failed without changing `ocr_status`.

- **Step 3.5 - Handle apply progress callbacks.** *(Analysis Section 2 `./src/webapp/backend/workflow.py`; Section 3 Stage State Boundary)*  
  Add `_handle_apply_progress(event: ApplyProgressEvent)`. Map `item_start` to active item `running`, `item_complete` to `done`, `item_failed` to `failed`, and keep `progress.stage == "merge"`. Broadcast after every state change using the existing `_broadcast` pattern.

- **Step 3.6 - Load and validate merge results after apply completes.** *(Analysis Section 2 `./src/webapp/backend/workflow.py`; Section 3 Result Loading Boundary)*  
  Add helpers to read `batch_mrg_result.json`, require a top-level object with `items: list`, and convert items to the backend result models. Missing, unreadable, malformed, or invalid result files after apply completion must set `merge_status="failed"`, `merge_results_available=False`, and `merge_result_error`, not an empty successful result list. Group-scoped failed items inside a valid result file should keep `merge_status="complete"` and `merge_results_available=True`.

- **Step 3.7 - Add result preview resolution helpers.** *(Analysis Section 2 `./src/webapp/backend/workflow.py`; Section 3 Preview Boundary, Filesystem Safety)*  
  Add backend-validated result ids, preferably base64-encoding `[item_index, output_pdf, output_markdown]` or separate artifact paths. Resolve only relative `output_pdf` and `output_markdown` under the configured output/apply directory using the same traversal checks as `_resolve_output_file`. Provide separate helpers for result PDF file paths and result Markdown content.

- **Step 3.8 - Add FastAPI routes.** *(Analysis Section 2 `./src/webapp/backend/app.py`; Section 3 Error Handling)*  
  In `src/webapp/backend/app.py`, add `POST /api/workflow/merge` accepting the merge request model and returning `WorkflowState`; add `GET /api/workflow/merge-results`; add preview routes for result PDFs and result Markdown. Reuse existing `SettingsStoreError`, `ValidationError`, `WorkflowServiceError`, and `JSONResponse` patterns. Return 409 for duplicate/running workflow conflicts and 400/404/500 according to service errors.

**Exit Criterion:** The backend can start merge from the submitted editable plan, persist it atomically, run apply in the existing worker model, publish merge progress through state/SSE, expose validated final results, and serve only safe PDF/Markdown result previews.

**Validation Command:** `uv run pytest test/webapp_tests/test_workflow_api.py -q`

## Phase 4: Replace Frontend Merge Simulation with Backend Merge
**Traceability:** Implements Analysis Section 2 `./src/webapp/frontend/src/types.ts`, Section 2 `./src/webapp/frontend/src/api.ts`, Section 2 `./src/webapp/frontend/src/components/WorkflowPanel.tsx`, Section 2 stylesheet updates, and Section 3 Stage State Boundary, Preview Boundary, Editable Plan Boundary, and Concurrency.

### Steps
- **Step 4.1 - Mirror backend types.** *(Analysis Section 2 `./src/webapp/frontend/src/types.ts`)*  
  In `src/webapp/frontend/src/types.ts`, extend `WorkflowProgress.stage` with `"merge"`; add `merge_status`, `active_merge_item_id`, `merge_items`, `merge_results_available`, and `merge_result_error` to `WorkflowState`; replace placeholder `MergeRow` with real merge progress/result types. Result types must model PDF and Markdown previews only.

- **Step 4.2 - Add merge API helpers.** *(Analysis Section 2 `./src/webapp/frontend/src/api.ts`; Section 3 Editable Plan Boundary)*  
  Add `startWorkflowMerge(plan: EditableMergePlan): Promise<WorkflowState>` that posts `{ plan }` to `/api/workflow/merge`. Add `fetchMergeResults()`, `buildMergeResultPdfPreviewUrl(result)`, and `fetchMergeResultMarkdown(result)`. Keep existing merge-plan load/save helpers for OCR-stage editing, but merge start must post the in-memory plan directly.

- **Step 4.3 - Update stage derivation.** *(Analysis Section 2 `./src/webapp/frontend/src/components/WorkflowPanel.tsx`; Section 3 Stage State Boundary)*  
  Make Merge stage state derive from `workflowState.merge_status`. OCR completion should enable Merge; merge running should own the active progress indicator with `workflowState.progress.stage === "merge"`; OCR should not appear active once merge starts. Rename becomes enabled only after merge reaches the intended terminal/result-ready state.

- **Step 4.4 - Replace `runMergeStage`.** *(Analysis Section 2 `./src/webapp/frontend/src/components/WorkflowPanel.tsx`; Section 3 Editable Plan Boundary)*  
  Remove the save-then-`runSimulatedStage('merge')` behavior. `runMergeStage` should validate that `editablePlan` exists, select Merge, call `startWorkflowMerge(editablePlan)`, update `workflowState`, and keep the current editable plan displayed while the worker runs. Leave rename simulation untouched unless needed for type compatibility.

- **Step 4.5 - Render merge progress and final result rows.** *(Analysis Section 2 `./src/webapp/frontend/src/components/WorkflowPanel.tsx`; Section 3 Result Loading Boundary)*  
  While `merge_status === "running"` or results are not available, render the editable top-level group/PDF list with status badges from `workflowState.merge_items`: pending neutral, running highlighted, done green, failed red. After `merge_results_available` is true, fetch result rows from `/api/workflow/merge-results` and render final result rows. Preserve failed result labels and messages.

- **Step 4.6 - Split OCR selection from merge result selection.** *(Analysis Section 2 `./src/webapp/frontend/src/components/WorkflowPanel.tsx`; Section 3 Preview Boundary)*  
  Keep OCR plan selection for OCR previews. Add separate selected merge result state if needed. Middle/right panels should show OCR source/Markdown during OCR, but for Merge results show only final PDF and final Markdown from result routes. Do not show image preview controls or image fallbacks for merge result rows.

- **Step 4.7 - Preserve disabled interactions during merge.** *(Analysis Section 2 `./src/webapp/frontend/src/components/WorkflowPanel.tsx`; Section 3 Concurrency)*  
  Reuse existing `isStageRunning` gates so row clicks, drag/drop, group toggles that mutate state, and stage buttons are disabled or ignored while merge runs. Keep the group list visible while disabled.

- **Step 4.8 - Add styles matching current workflow language.** *(Analysis Section 2 stylesheet updates)*  
  In `src/webapp/frontend/src/App.css` or the existing workflow stylesheet, add status classes for merge pending/running/done/failed and result/failure labels. Use current semantic colors: done green, failed red, pending neutral, running highlighted.

**Exit Criterion:** The frontend starts real backend merge with the current in-memory editable plan, shows backend merge progress, switches to final result rows only after backend result availability, and previews only final PDFs/Markdown for merge outputs.

**Validation Command:** `Push-Location src/webapp/frontend; npm run build; Pop-Location`

## Phase 5: Add Focused Tests and Documentation
**Traceability:** Implements Analysis Section 2 tests/docs and all Analysis Section 4 verification checklist items.

### Steps
- **Step 5.1 - Add apply unit tests.** *(Analysis Section 2 `./test/md_mrg/test_mrg_units.py`; Section 4)*  
  Add tests for apply progress event order, PDF copy from original source into output/apply folder, original PDF preservation, overwrite-enabled replacement, overwrite-disabled collision, enriched result fields, and continued processing after failed groups. Update existing tests only where the new source/output distinction changes expectations.

- **Step 5.2 - Add backend workflow API tests.** *(Analysis Section 2 `./test/webapp_tests/test_workflow_api.py`; Section 4)*  
  Add tests for merge-start preconditions, duplicate worker conflict, atomic rewrite from posted plan before `run_apply`, invalid plan not mutating `batch_mrg.json`, `merge_status == "running"`, `progress.stage == "merge"`, progress callback item status transitions, successful result loading, malformed/missing result failure, failed result item display readiness, and preview path safety. Monkeypatch `webapp.backend.workflow.md_mrg_apply.run_apply` for deterministic worker behavior.

- **Step 5.3 - Verify CLI/config path behavior.** *(Analysis Section 2 `./test/md_mrg/test_mrg_plan.py`; Section 4)*  
  Add or update CLI/config tests only if config semantics changed. Confirm `md-mrg --apply` remains compatible and `--plan` behavior/exit codes are not regressed.

- **Step 5.4 - Add frontend type/test coverage available in this repo.** *(Analysis Section 2 frontend test/typecheck surface; Section 4)*  
  If no frontend test runner exists, rely on `npm run build` for TypeScript contract validation. If a test harness is added later, cover merge API calls, merge-running disabled interaction, group status rendering, result switching, and PDF/Markdown-only preview behavior.

- **Step 5.5 - Update `docs/internals/md_mrg.md`.** *(Analysis Section 2 `./docs/internals/md_mrg.md`; Section 3 PDF Copy Ownership)*  
  Document apply ownership of PDF copy/overwrite behavior, source/output path semantics, result payload fields, progress granularity, and failed group semantics. Remove stale wording that says standalone PDFs are only passthrough status items if apply now copies final artifacts for preview.

**Exit Criterion:** Tests cover the new apply, backend workflow, preview safety, and frontend type contracts; docs accurately describe the new apply/result behavior.

**Validation Command:** `uv run pytest test/md_mrg test/webapp_tests/test_workflow_api.py`

## Phase 6: Final End-to-End Verification
**Traceability:** Implements Analysis Section 4 full verification checklist.

### Steps
- **Step 6.1 - Run focused Python verification.** *(Analysis Section 4)*  
  Run:
  ```powershell
  uv run pytest test/md_mrg test/webapp_tests/test_workflow_api.py
  ```

- **Step 6.2 - Run frontend contract verification.** *(Analysis Section 4)*  
  Run:
  ```powershell
  Push-Location src/webapp/frontend; npm run build; Pop-Location
  ```

- **Step 6.3 - Run broader regression if focused checks pass.** *(Analysis Section 4)*  
  Run:
  ```powershell
  uv run pytest
  ```
  If this exposes unrelated pre-existing failures, document them separately and keep the merge implementation focused.

- **Step 6.4 - Manual workflow smoke check.** *(Analysis Sections 1, 3, 4)*  
  Start the webapp, run Start -> OCR/planning with a small fixture folder, edit the merge tree in memory, click Merge, verify the group list stays visible and disabled while progress events arrive, then verify final PDF/Markdown result previews load from `batch_mrg_result.json`.

**Exit Criterion:** Focused Python tests, frontend build, and available broader regression checks pass or have documented unrelated failures; manual smoke confirms the user-facing merge flow no longer uses placeholders.

**Validation Command:** `uv run pytest; Push-Location src/webapp/frontend; npm run build; Pop-Location`