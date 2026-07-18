# Implementation Plan: wire-ocr-stage

> **Core Objective:** Detailed step-by-step technical execution blueprint for implementing the requirements specified in the analysis.

## Traceability

- **Analysis Reference:** [Analysis Reference](./wire-ocr-stage.plan.analysis.md)
- **Issue Name:** `wire-ocr-stage`
- **Scope Guard:** Implement real OCR-stage execution from the existing webapp Workflow panel through `md_gen` generation and `md_mrg` planning only. Keep Merge and Rename as placeholders unless explicitly enabled by existing post-OCR state rules. Preserve default CLI behavior and do not parse human-readable CLI logs.
- **Current Code Anchors:** `md_gen.foundation.run_foundation_bootstrap`, `md_gen.page_processor.process_file`, `md_mrg.planner.run_plan`, `webapp.backend.workflow.discover_start`, `webapp.backend.app.create_app`, `WorkflowPanel.tsx`.

## Phase 1: Domain Progress Contracts for `md_gen`

Implementing requirements from Analysis Sections 1 Data Flow/New Architectural Pattern, 2 `src/md_gen/foundation.py`, 2 `src/md_gen/page_processor.py`, 2 `src/md_gen/cli.py`, and 3 CLI Compatibility/Zero Work Cases/Data Contract Edges.

### Steps

1. Implementing Analysis Sections 1 and 2 `src/md_gen/foundation.py`: add a typed callback contract near the generation boundary, using stdlib dataclasses or `TypedDict` consistently with the module style. Keep it small and stable:
   ```python
   GenerationProgressKind = Literal[
       "stage_start", "ocr_item_start", "ocr_item_complete", "batch_persisted", "complete", "failed"
   ]
   GenerationProgressCallback = Callable[[GenerationProgressEvent], None]
   ```
   Include fields for `kind`, `total_jobs`, `completed_jobs`, `markdown_count`, `source_path`, `source_file_name`, `source_type`, `page_number`, `markdown_path`, `error_code`, and `message` where applicable.
2. Implementing Analysis Section 2 `src/md_gen/foundation.py`: introduce a reusable entrypoint, for example `run_generation(config: AppConfig, progress_callback: GenerationProgressCallback | None = None) -> int`, and make `run_foundation_bootstrap(config)` a CLI-compatible wrapper that calls it without a callback.
3. Implementing Analysis Sections 2 `src/md_gen/foundation.py` and 2 `src/md_gen/page_processor.py`: count total OCR jobs before processing. Use `build_work_items(config)`, count each image as one job, and count each PDF using `rasterizer.get_pdf_page_count(path)`. If page counting fails, let the generation entrypoint emit a failed event and return the same runtime failure code path currently used by `run_foundation_bootstrap`.
4. Implementing Analysis Section 2 `src/md_gen/page_processor.py`: split the page loop enough to report page-level progress around the real rasterize/OCR/summarize work. Prefer extending `process_file` with optional callback/context parameters over duplicating processing logic:
   ```python
   def process_file(
       config: AppConfig,
       file_item: FileItem,
       *,
       progress_callback: GenerationProgressCallback | None = None,
       progress_context: GenerationProgressContext | None = None,
   ) -> dict[str, Any]: ...
   ```
5. Implementing Analysis Sections 2 `src/md_gen/page_processor.py` and 3 Data Contract Edges: increment `completed_jobs` and `markdown_count` once per completed PDF page or standalone image. Keep the returned metadata document-level shape compatible with existing `batch.json`: one document record per source file, including `source_file_name`, `file_type`, `page_count`, `summary`, `markdown_file`, and `status`.
6. Implementing Analysis Sections 2 `src/md_gen/foundation.py` and 3 Error Handling: emit `failed` events for configuration, gateway, and runtime failures without emitting `complete`. Preserve exit codes: config validation `2`, gateway `4`, unexpected runtime `1`, success `0`.
7. Implementing Analysis Section 2 `src/md_gen/cli.py`: keep `main()` as argument parsing, verbose config dump, and call into the wrapper. Do not add machine-readable CLI output unless implementation truly needs it; if added, make it opt-in and test default stdout compatibility.
8. Implementing Analysis Section 4 Verification Checklist: add or update tests in `test/md_gen/test_page_processor.py` and `test/md_gen/test_cli.py` for PDF page job counting, standalone image job counting, callback event order, failure events, batch persistence, and unchanged CLI behavior.

### Exit Criterion

`md_gen` exposes an in-process callback-capable generation entrypoint, reports OCR jobs per PDF page/image, still writes `batch.json` with the existing metadata contract, and the CLI remains compatible by default.

### Validation Command

```powershell
uv run pytest test/md_gen/test_page_processor.py test/md_gen/test_cli.py
```

## Phase 2: Domain Progress Contracts for `md_mrg`

Implementing requirements from Analysis Sections 1 Data Flow/New Architectural Pattern, 2 `src/md_mrg/planner.py`, 2 `src/md_mrg/cli.py`, and 3 Zero Work Cases/Data Contract Edges/CLI Compatibility.

### Steps

1. Implementing Analysis Section 2 `src/md_mrg/planner.py`: add a typed planning callback contract adjacent to `PlannerError`/`ScoreOutcome`:
   ```python
   PlanningProgressKind = Literal[
       "plan_start", "comparison_start", "comparison_complete", "plan_persisted", "complete", "failed"
   ]
   PlanningProgressCallback = Callable[[PlanningProgressEvent], None]
   ```
   Include `total_comparisons`, `completed_comparisons`, left/right source identifiers or names, score status/outcome, `pdf_document_count`, `image_group_count`, `error_code`, and `message` where available.
2. Implementing Analysis Sections 2 `src/md_mrg/planner.py` and 3 Data Contract Edges: extend `run_plan(source_dir: Path, cfg: AppConfig, progress_callback: PlanningProgressCallback | None = None) -> dict[str, Any]`. Keep the existing positional call sites working by making the callback keyword-only or optional.
3. Implementing Analysis Section 2 `src/md_mrg/planner.py`: after `_partition_documents`, compute `total_comparisons = max(len(image_documents) - 1, 0)` and `pdf_document_count = len(pdf_documents)`. Emit `plan_start` before gateway comparisons.
4. Implementing Analysis Section 2 `src/md_mrg/planner.py`: thread the callback into `_build_groups` or create a small adjacent helper so `comparison_start` is emitted before `_score_pair` and `comparison_complete` after the score outcome is known. Do not move PDF records into comparison progress.
5. Implementing Analysis Sections 2 `src/md_mrg/planner.py` and 3 Zero Work Cases: ensure zero-image and one-image inputs emit deterministic progress and still persist a valid `batch_mrg.json` when current planner rules allow it.
6. Implementing Analysis Section 3 Data Contract Edges: derive final `image_group_count` from the group objects generated from image documents only, before appending PDF records to `merged_documents`.
7. Implementing Analysis Section 2 `src/md_mrg/cli.py`: keep `main()` behavior unchanged for `--plan` and `--apply`; call `run_plan(source_dir=config.paths.source_dir, cfg=config)` without a callback.
8. Implementing Analysis Section 4 Verification Checklist: update `test/md_mrg/test_mrg_plan.py` to assert comparison totals, active pair event payloads, zero/one image behavior, PDF count exclusion from comparison progress, final image group count, and unchanged CLI dispatch/error behavior.

### Exit Criterion

`md_mrg` planning exposes callback progress for adjacent image comparisons, handles zero/one image cases without division or stale active pair state, persists `batch_mrg.json`, and preserves CLI behavior.

### Validation Command

```powershell
uv run pytest test/md_mrg/test_mrg_plan.py --no-cov
```

## Phase 3: Backend Workflow State Models and Orchestration Service

Implementing requirements from Analysis Sections 1 State Ownership Change/Real-Time Transport Decision, 2 `src/webapp/backend/models.py`, 2 `src/webapp/backend/workflow.py`, and 3 Error Handling/Security/Performance/Concurrency/State Recovery.

### Steps

1. Implementing Analysis Section 2 `src/webapp/backend/models.py`: add backend-owned workflow state schemas while preserving `WorkflowDiscoveryResponse`. Recommended model set:
   ```python
   WorkflowStageStatus = Literal["idle", "enabled", "running", "complete", "failed"]
   WorkflowActiveItem(BaseModel): source_id, display_name, source_type, page_number, markdown_file
   WorkflowActiveComparison(BaseModel): left_source_id, right_source_id, left_display_name, right_display_name
   WorkflowCounts(BaseModel): markdown_count, pdf_document_count, image_group_count
   WorkflowProgress(BaseModel): stage, total_jobs, completed_jobs, percent
   WorkflowState(BaseModel): discovery, ocr_status, progress, counts, current_item, active_comparison, messages, error
   ```
   Use snake_case fields to match current frontend conventions.
2. Implementing Analysis Sections 1 and 2 `src/webapp/backend/workflow.py`: replace the purely stateless module shape with a `WorkflowService` class that still owns discovery and preview helpers. Keep module-level `discover_start`/`resolve_preview_path` wrappers only if existing route tests need compatibility, but route wiring should use the service instance.
3. Implementing Analysis Sections 2 `src/webapp/backend/workflow.py` and 3 State Recovery: store the latest `WorkflowState` in memory for the single local app process. Protect state with a `threading.Lock` or `asyncio.Lock` consistently with the execution model.
4. Implementing Analysis Sections 2 `src/webapp/backend/workflow.py` and 3 Concurrency: enforce one active OCR run. A second OCR start while `ocr_status == "running"` should return the current state or raise a clear 409-style service error; choose one behavior and test it.
5. Implementing Analysis Sections 2 `src/webapp/backend/workflow.py` and 3 Error Handling: add `start_ocr(settings: AppSettings) -> WorkflowState` plus a background worker method. Validate that the latest discovery exists, `discovery.ok is True`, `discovery.metrics.total_count > 0`, and the output folder setting resolves to a writable directory or can be created according to current CLI semantics.
6. Implementing Analysis Section 2 `src/webapp/backend/workflow.py`: build the real runtime `AppConfig` from `AppSettings`, not the current discovery-only dry-run adapter. Read `settings.md_gen.summary.prompt_path` and `settings.md_mrg.score.prompt_path` into `PromptSettings.summary_prompt_text`; set `RuntimeSettings(dry_run=False, overwrite=settings.overwrite)`.
7. Implementing Analysis Section 1 Data Flow: call domain code in order inside the worker: `md_gen.foundation.run_generation(config, progress_callback=...)`, verify `output_dir / "batch.json"`, then call `md_mrg.planner.run_plan(source_dir=config.paths.output_dir, cfg=config, progress_callback=...)`.
8. Implementing Analysis Sections 1 and 2 `src/webapp/backend/workflow.py`: translate generation callback events into normalized state. Map generation percent to 0-50 using `completed_jobs / total_jobs`, update `counts.markdown_count`, set `current_item`, clear `active_comparison`, append concise user-facing messages, and broadcast after each state mutation.
9. Implementing Analysis Sections 1 and 2 `src/webapp/backend/workflow.py`: translate planning callback events into normalized state. Map planning percent to 50-100, set `active_comparison` during comparison events, update `counts.pdf_document_count` from `batch.json`, and update `counts.image_group_count` from `batch_mrg.json` when persisted or complete.
10. Implementing Analysis Sections 3 Error Handling and 4 Verification Checklist: if generation returns non-zero or `batch.json` is missing/invalid, mark OCR failed and do not call planning. If planning raises `PlannerError` or returns invalid output, mark OCR failed after generation. On success, set progress to 100, `ocr_status="complete"`, clear `current_item` and `active_comparison`, and leave retry behavior as a full OCR rerun.
11. Implementing Analysis Section 1 Real-Time Transport Decision: add subscription/broadcast support for SSE consumers. Use lightweight queues per subscriber and ensure the latest state is sent immediately on subscription. Remove subscriber queues on disconnect.
12. Implementing Analysis Section 4 Verification Checklist: extend `test/webapp_tests/test_workflow_api.py` with monkeypatched fake generation/planning functions that emit progress callbacks, write minimal `batch.json`/`batch_mrg.json`, and assert state transitions without real OCR/model calls.

### Exit Criterion

The backend has a single local workflow service that owns discovery-derived OCR availability, executes generation then planning in a background path, normalizes progress/counts/state, handles failures deterministically, and can broadcast snapshots to subscribers.

### Validation Command

```powershell
uv run pytest test/webapp_tests/test_workflow_api.py
```

## Phase 4: Backend Routes and SSE Delivery

Implementing requirements from Analysis Sections 1 Real-Time Transport Decision, 2 `src/webapp/backend/app.py`, and 3 Error Handling/Security/Performance/Concurrency.

### Steps

1. Implementing Analysis Section 2 `src/webapp/backend/app.py`: construct one `WorkflowService` inside `create_app(settings_path=..., defaults_path=..., allowed_origins=...)` so tests can create isolated app instances. Existing settings/default path injection must keep working.
2. Implementing Analysis Sections 2 `src/webapp/backend/app.py` and 3 Error Handling: keep `POST /api/workflow/start` compatible by loading settings, calling the service discovery method, storing the discovery snapshot in service state, invalidating previous OCR/Merge/Rename state, and returning `WorkflowDiscoveryResponse` as today.
3. Implementing Analysis Section 2 `src/webapp/backend/app.py`: add `POST /api/workflow/ocr` returning the latest `WorkflowState`. It should load settings, delegate to `workflow_service.start_ocr(settings)`, and map validation/conflict failures to JSON errors or failed state responses consistently with tests.
4. Implementing Analysis Section 2 `src/webapp/backend/app.py`: add `GET /api/workflow/state` returning the latest `WorkflowState`, including idle defaults before Start has run.
5. Implementing Analysis Sections 1 and 2 `src/webapp/backend/app.py`: add `GET /api/workflow/events` as `text/event-stream`. Use `StreamingResponse` with serialized JSON events in SSE format:
   ```text
   event: workflow_state
   data: {...}

   ```
   Send the current state immediately, then stream subsequent service broadcasts until disconnect.
6. Implementing Analysis Sections 2 `src/webapp/backend/app.py` and 3 Security: preserve `/api/workflow/source-preview/{file_id}` behavior and validation. Do not accept arbitrary OCR source/output paths in the OCR request; use saved settings only.
7. Implementing Analysis Section 3 Performance: ensure `POST /api/workflow/ocr` starts the long-running worker and returns promptly, so SSE and unrelated API requests are not blocked.
8. Implementing Analysis Section 4 Verification Checklist: add API tests for snapshot before Start, OCR unavailable before successful non-empty discovery, OCR start order, failure response/state, final complete state, conflict behavior, and SSE first event delivery.

### Exit Criterion

The webapp exposes compatible Start/preview routes plus OCR start, state snapshot, and SSE stream routes backed by one workflow service instance per app factory instance.

### Validation Command

```powershell
uv run pytest test/webapp_tests/test_workflow_api.py
```

## Phase 5: Frontend Types and API Client

Implementing requirements from Analysis Sections 1 Data Flow, 2 `src/webapp/frontend/src/types.ts`, 2 `src/webapp/frontend/src/api.ts`, and 3 State Recovery/Data Contract Edges.

### Steps

1. Implementing Analysis Section 2 `src/webapp/frontend/src/types.ts`: mirror the backend `WorkflowState` models exactly with snake_case field names. Add types for OCR status, progress, counts, active item, active comparison pair, and messages. Preserve existing discovery and settings interfaces.
2. Implementing Analysis Section 2 `src/webapp/frontend/src/types.ts`: expand display status unions so OCR rows can represent backend-driven states such as `pending`, `running`, `complete`, and `failed`, while Merge/Rename placeholder types remain compatible.
3. Implementing Analysis Section 2 `src/webapp/frontend/src/api.ts`: add `startWorkflowOcr(): Promise<WorkflowState>` calling `POST /api/workflow/ocr`, `fetchWorkflowState(): Promise<WorkflowState>` calling `GET /api/workflow/state`, and an exported `WORKFLOW_EVENTS_URL = "/api/workflow/events"` or a small `createWorkflowEventSource()` helper.
4. Implementing Analysis Sections 2 `src/webapp/frontend/src/api.ts` and 3 Error Handling: keep the current `{detail}` error parsing pattern for non-OK responses. Do not hide failed workflow state payloads if the backend returns them with HTTP 200.
5. Implementing Analysis Section 3 State Recovery: ensure the API surface supports initial snapshot recovery before or alongside opening EventSource.

### Exit Criterion

Frontend code has typed access to OCR start, workflow snapshot, and SSE endpoint contracts without reshaping backend field names or changing existing settings/discovery API behavior.

### Validation Command

```powershell
Push-Location src/webapp/frontend; npm run build; Pop-Location
```

## Phase 6: Frontend Workflow Panel Integration

Implementing requirements from Analysis Sections 1 Data Flow, 2 `src/webapp/frontend/src/components/WorkflowPanel.tsx`, 2 `src/webapp/frontend/src/styles.css`, and 3 State Recovery/Data Contract Edges.

### Steps

1. Implementing Analysis Section 2 `WorkflowPanel.tsx`: on component mount, fetch `GET /api/workflow/state`, then open `EventSource(WORKFLOW_EVENTS_URL)`. Apply every `workflow_state` event to local `workflowState`. Close EventSource on unmount.
2. Implementing Analysis Sections 2 `WorkflowPanel.tsx` and 3 State Recovery: if SSE errors, keep the latest state and fetch a snapshot as recovery. Avoid restarting OCR from snapshot or reconnect handling.
3. Implementing Analysis Section 2 `WorkflowPanel.tsx`: update `runStart()` so a new Start discovery clears OCR/Merge/Rename placeholder rows, stores the returned discovery, resets selected source, invalidates local downstream placeholder state, and relies on discovery success with `metrics.total_count > 0` to enable OCR.
4. Implementing Analysis Section 2 `WorkflowPanel.tsx`: replace only the OCR branch of `runSimulatedStage` with real `startWorkflowOcr()`. Keep Merge and Rename placeholder behavior unchanged unless the existing state rules enable them after OCR completion.
5. Implementing Analysis Sections 1 and 2 `WorkflowPanel.tsx`: derive OCR button state and progress rail from backend `workflowState.ocr_status` and `workflowState.progress.percent`. Keep the visible primary stage label as `OCR`; put substage details only in status text.
6. Implementing Analysis Sections 2 `WorkflowPanel.tsx` and 3 Data Contract Edges: render OCR metrics from backend counts: Markdown Files from `counts.markdown_count`, PDF Documents from `counts.pdf_document_count`, Image Groups from `counts.image_group_count`. Remove placeholder formulas such as `Math.ceil(metrics.image_count / 3)` for OCR.
7. Implementing Analysis Section 2 `WorkflowPanel.tsx`: render user-facing messages for current OCR item and comparison pair. Example messages: `Processing invoice.pdf page 2` and `Comparing scan-01.jpg with scan-02.jpg`.
8. Implementing Analysis Section 2 `WorkflowPanel.tsx`: highlight source rows when `workflowState.current_item.source_id` matches the item id and when either active comparison id matches. Preserve selected-row behavior when selected and active states overlap.
9. Implementing Analysis Section 2 `styles.css`: add classes for active OCR rows, active comparison rows, backend-running, backend-failed, and backend-complete progress/status states inside the existing Tailwind/component style conventions.
10. Implementing Analysis Section 3 Data Contract Edges: do not display internal `md_gen` or `md_mrg` stage names as primary stage controls. Keep Merge/Rename placeholder copy honest and do not imply merge/apply or rename has been implemented.

### Exit Criterion

The Workflow panel starts real OCR from the OCR control, receives live backend state through SSE, renders backend counts/progress/status/highlights, recovers from snapshot without rerunning work, and keeps Merge/Rename placeholder behavior intact.

### Validation Command

```powershell
Push-Location src/webapp/frontend; npm run build; Pop-Location
```

## Phase 7: Frontend Tests or Focused UI Validation

Implementing requirements from Analysis Sections 2 `src/webapp/frontend/package.json`, 2 `WorkflowPanel` test file, and 4 Verification Checklist.

### Steps

1. Implementing Analysis Section 2 `src/webapp/frontend/package.json`: first check whether frontend test tooling already exists. It currently has `dev`, `build`, and `preview` scripts only. If adding component tests, add a deliberate test stack such as Vitest + React Testing Library + jsdom and a `test` script.
2. Implementing Analysis Section 2 `WorkflowPanel` test file: if the test stack is added, create a colocated or conventional test file for `WorkflowPanel` that mocks `fetch`, `EventSource`, discovery, OCR start, snapshot, and SSE updates.
3. Implementing Analysis Section 4 Verification Checklist: cover OCR enabled after non-empty Start discovery, OCR start API call, snapshot/SSE count rendering, active OCR row highlighting, active comparison highlighting, OCR failure messages, and preservation of Merge/Rename placeholder behavior.
4. Implementing Analysis Section 2 `src/webapp/frontend/package.json`: if frontend test tooling is not added in this implementation pass, document that decision in the final coding-phase response and rely on `npm run build` plus backend API tests for automated validation.

### Exit Criterion

Either focused frontend component tests exist and pass, or the implementation explicitly records why frontend test tooling was not introduced and validates the typed frontend integration through a successful production build.

### Validation Command

```powershell
Push-Location src/webapp/frontend; npm run build; $scripts = (Get-Content package.json | ConvertFrom-Json).scripts; if ($scripts.PSObject.Properties.Name -contains "test") { npm run test -- --run }; Pop-Location
```

## Phase 8: End-to-End Backend State Verification and Regression Sweep

Implementing requirements from Analysis Sections 3 Boundary & Edge Case Analysis and 4 Verification Checklist.

### Steps

1. Implementing Analysis Section 4 Verification Checklist: run the focused Python tests for domain callbacks and workflow API after all backend changes are integrated.
2. Implementing Analysis Section 4 Verification Checklist: run the frontend build after all type/API/component changes are integrated.
3. Implementing Analysis Sections 3 and 4: manually or with tests confirm these edge states: zero supported discovery leaves OCR unavailable, generation failure stops planning, planning failure marks OCR failed after generation, success reaches 100% and clears active item/pair, and SSE sends the latest state immediately.
4. Implementing Analysis Section 3 Security: confirm preview route still rejects traversal/outside/unsupported/missing files and OCR start still uses saved settings rather than request-provided paths.
5. Implementing Analysis Section 3 CLI Compatibility: run or keep passing existing CLI tests for `md-gen` and `md-mrg` so callback additions do not change default command output or exit code behavior.

### Exit Criterion

All touched backend/domain/frontend slices validate, the behavior checklist from the analysis is covered by tests or explicit manual checks, and no unrelated workflow stages are implemented beyond OCR orchestration.

### Validation Command

```powershell
uv run pytest test/md_gen/test_page_processor.py test/md_gen/test_cli.py test/md_mrg/test_mrg_plan.py test/webapp_tests/test_workflow_api.py --no-cov
Push-Location src/webapp/frontend; npm run build; Pop-Location
```
