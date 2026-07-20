# Implementation Analysis: wire-ocr-stage

## 1. Architectural Impact & Data Flow
*High-level overview of how data flows through the system for this feature. Identify any new patterns or structural additions.*
- **Affected Subsystems:** `md_gen` processing pipeline, `md_mrg` merge-planning pipeline, shared configuration mapping, FastAPI workflow backend, backend Pydantic API schemas, frontend workflow API client, frontend workflow state/types, existing workflow panel UI, CSS state styling, Python unit/API tests, and frontend interaction tests.
- **Data Flow Changes:** User clicks `Start` -> backend loads settings -> `discover_start` scans source files -> frontend stores discovery snapshot and enables `OCR` only when discovery succeeds with at least one supported item -> user clicks `OCR` -> backend validates current settings/discovery/output folder -> backend creates or updates an in-memory workflow run state -> backend calls reusable `md_gen` processing function in-process with a structured progress callback -> `md_gen` emits OCR job start/complete events for PDF pages and standalone images -> backend maps generation progress to overall OCR progress from 0% to 50%, updates Markdown count and current source item, and broadcasts state -> backend verifies `batch.json` -> backend calls reusable `md_mrg` planning function in-process with a structured progress callback -> `md_mrg` emits adjacent image comparison start/complete events -> backend maps planning progress to 50% through 100%, updates PDF document count from `batch.json`, active comparison pair, and image group count from `batch_mrg.json` -> backend marks OCR complete and enables subsequent workflow state according to existing rules -> frontend receives state snapshots through Server-Sent Events and renders progress, counts, active document highlighting, active comparison highlighting, and status messages in the existing workflow layout.
- **New Architectural Pattern:** Add typed structured progress events at the domain-module boundary. `md_gen` and `md_mrg` remain owners of OCR and planning logic, while the webapp backend becomes an orchestration and state-normalization layer. CLI output remains human-oriented by default; any machine-readable progress emission must be optional and separate from the backend callback path.
- **Real-Time Transport Decision:** Add Server-Sent Events for one-way workflow state delivery. SSE fits the requirement because the browser only needs server-to-client progress updates, cancellation is out of scope, and the existing snapshot endpoint can remain the recovery source for reconnects or initial page loads.
- **State Ownership Change:** The backend needs workflow state beyond the current stateless discovery response. Discovery, OCR status, progress, counts, current item, active comparison pair, messages, and final artifacts should be represented as a normalized workflow state model that both snapshot and SSE endpoints can serialize.

## 2. Component & File Impact Map
*Identify the exact files that must be created, modified, or deleted, and what structural changes they require.*

### `./src/md_gen/foundation.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Introduce a reusable Markdown generation entrypoint that accepts an optional progress callback while preserving the existing CLI-facing bootstrap behavior.
  - [ ] Define or import a stable structured progress event shape for generation lifecycle events such as stage start, OCR item start, OCR item complete, batch persisted, complete, and failed.
  - [ ] Ensure progress event payloads include total OCR jobs, completed OCR jobs, generated Markdown count, source file name/path, source type, page number for PDFs, and generated Markdown path/name when available.
  - [ ] Keep CLI-compatible text output behavior separated from callback emission.
- **Logic Modifications Required:**
  - [ ] Count total OCR jobs before processing using PDF page counts plus standalone image files, not merely top-level discovered file count.
  - [ ] Emit deterministic progress when no supported OCR jobs are found.
  - [ ] Emit completion or failure events without reporting partial outputs as successful OCR completion.
  - [ ] Preserve `batch.json` generation semantics and existing error exit-code mapping for CLI callers.

### `./src/md_gen/page_processor.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Accept optional progress reporting context or callback data from the generation entrypoint.
  - [ ] Expose enough per-page information for the generation entrypoint to emit page-level job start and completion events.
  - [ ] Ensure output metadata can still represent multi-page PDF outputs while Markdown count increments per page/image OCR job as required by the UI.
- **Logic Modifications Required:**
  - [ ] Report OCR progress around the actual page rasterization/OCR/summarization unit of work.
  - [ ] Keep current document metadata fields compatible with `batch.json` consumers.
  - [ ] Avoid conflating top-level source files with OCR jobs when PDFs contain multiple pages.

### `./src/md_gen/cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Keep `main()` as a thin wrapper over the reusable generation function.
  - [ ] Optionally add an explicit machine-readable progress flag only if CLI progress output is required during implementation.
- **Logic Modifications Required:**
  - [ ] Preserve current default CLI behavior and existing parser/verbose behavior.
  - [ ] Continue returning compatible exit codes for configuration errors, gateway errors, and runtime errors.

### `./src/md_mrg/planner.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Extend `run_plan` or an adjacent reusable planning entrypoint to accept an optional progress callback.
  - [ ] Define or import a stable structured progress event shape for planning lifecycle events such as plan start, comparison start, comparison complete, plan persisted, complete, and failed.
  - [ ] Include total comparison jobs, completed comparison jobs, source document identifiers/names for both compared images, score outcome status, PDF document count, and final image group count where available.
- **Logic Modifications Required:**
  - [ ] Compute comparison total as `max(len(image_documents) - 1, 0)`.
  - [ ] Emit active pair events around adjacent image comparison operations.
  - [ ] Emit deterministic complete progress for zero or one image document while still producing a valid plan payload when current planner rules allow it.
  - [ ] Keep PDF document records outside comparison work while exposing their count for backend state.
  - [ ] Derive final image group count from the plan output, counting detected image groups rather than appended PDF document records.

### `./src/md_mrg/cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Keep `main()` as a thin wrapper over reusable plan/apply functions.
  - [ ] Optionally add an explicit machine-readable progress flag for `--plan` only if needed, without changing default output.
- **Logic Modifications Required:**
  - [ ] Preserve current `--plan` and `--apply` mode behavior.
  - [ ] Preserve current planner/apply error handling and CLI exit-code behavior.

### `./src/webapp/backend/models.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add backend API schemas for normalized workflow state, OCR run status, OCR progress details, active source item, active comparison pair, workflow counts, and workflow messages.
  - [ ] Add schema fields that allow the frontend to distinguish discovered source files, current OCR parent document, and the two source documents participating in an image comparison.
  - [ ] Add status literals for idle, enabled, running, complete, and failed workflow stages if the existing frontend-only stage states become backend-owned.
  - [ ] Preserve `WorkflowDiscoveryResponse` for the Start stage or embed it in the broader workflow state model without breaking existing `/api/workflow/start` clients.
- **Logic Modifications Required:**
  - [ ] Ensure serialized state contains stage name, total jobs, completed jobs, current item, active comparison pair, Markdown count, PDF document count, image group count, overall percent, messages, and errors.
  - [ ] Ensure model defaults represent an idle workflow before discovery or OCR starts.

### `./src/webapp/backend/workflow.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add a workflow orchestration service that stores the latest workflow state in memory for the single local webapp session.
  - [ ] Add an OCR-start operation that validates discovery readiness and output folder settings, then invokes `md_gen` followed by `md_mrg` in-process.
  - [ ] Add callback adapters that translate `md_gen` and `md_mrg` progress events into the normalized backend workflow state.
  - [ ] Add state subscription/broadcast support for SSE consumers.
  - [ ] Keep discovery and preview path responsibilities intact.
- **Logic Modifications Required:**
  - [ ] Make discovery success with at least one supported item the controlling condition for OCR availability.
  - [ ] Invalidate OCR availability when settings/source paths change or when a new Start run replaces previous discovery.
  - [ ] Build runtime `AppConfig` values suitable for real processing, not the current discovery-only dry-run configuration.
  - [ ] Map generation progress to 0%-50% and planning progress to 50%-100%, with deterministic handling for zero-job substages.
  - [ ] Stop the OCR workflow before planning if Markdown generation fails or `batch.json` is absent/invalid.
  - [ ] Mark OCR failed if merge planning fails after generation and leave retry behavior as a full OCR rerun.
  - [ ] Clear current item and active comparison pair on successful completion.

### `./src/webapp/backend/app.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add an endpoint to start the OCR stage, likely under `/api/workflow/ocr` or a similarly scoped workflow route.
  - [ ] Add a snapshot endpoint that returns the latest normalized workflow state.
  - [ ] Add an SSE endpoint that streams workflow state changes and sends the latest state immediately on connection.
  - [ ] Inject or construct the workflow orchestration service in `create_app` so tests can control state and dependencies.
- **Logic Modifications Required:**
  - [ ] Convert orchestration and validation failures into appropriate JSON errors or failed workflow state responses.
  - [ ] Keep existing settings, discovery, and preview endpoints compatible.
  - [ ] Ensure long-running OCR execution does not block SSE delivery or unrelated API responses.

### `./src/webapp/frontend/src/types.ts`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add TypeScript interfaces mirroring backend workflow state, OCR progress, active item, active comparison pair, and stage/count status fields.
  - [ ] Expand row/status types beyond simulated placeholder states.
  - [ ] Represent backend-owned progress percentage and count values instead of deriving OCR metrics from placeholder rows.
- **Logic Modifications Required:**
  - [ ] Keep existing discovery response typing compatible with Start rendering.
  - [ ] Ensure active source IDs and comparison pair IDs can be matched against `WorkflowSourceFile.id` for list highlighting.

### `./src/webapp/frontend/src/api.ts`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add API client function for starting the OCR stage.
  - [ ] Add API client function for fetching workflow state snapshots.
  - [ ] Add SSE connection helper or endpoint constant for workflow events.
- **Logic Modifications Required:**
  - [ ] Surface backend validation/failure messages consistently with existing settings and discovery helpers.
  - [ ] Support snapshot recovery when SSE reconnects or fails.

### `./src/webapp/frontend/src/components/WorkflowPanel.tsx`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace the OCR branch of `runSimulatedStage` with a real OCR start call while leaving Merge and Rename placeholders untouched for this iteration.
  - [ ] Subscribe to workflow SSE updates and merge them with initial snapshot/discovery state.
  - [ ] Render OCR counts from backend workflow state: Markdown files, PDF documents, and Image Groups.
  - [ ] Render progress rail width from backend OCR progress while preserving the primary stage label as `OCR`.
  - [ ] Add active document and active comparison pair rendering states to the existing discovered document list.
  - [ ] Render user-friendly status messages such as current OCR file/page and current image comparison pair.
- **Logic Modifications Required:**
  - [ ] Enable OCR only after Start discovery succeeds with at least one supported item.
  - [ ] Clear OCR/Merge/Rename placeholder state when Start reruns or settings changes invalidate discovery.
  - [ ] Stop using placeholder formulas such as `Math.ceil(metrics.image_count / 3)` for image groups.
  - [ ] Keep internal sub-stage names out of primary stage controls while allowing descriptive status text.
  - [ ] Ensure late SSE connections and snapshot fetches render the latest state without restarting OCR.

### `./src/webapp/frontend/src/styles.css`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add visual states for active OCR document rows and active comparison pair rows in the existing source list.
  - [ ] Add or adjust progress/status styling for backend-driven running, failed, and complete states.
- **Logic Modifications Required:**
  - [ ] Keep row highlighting clear when a selected row is also active or part of the comparison pair.
  - [ ] Maintain responsive layout constraints for the existing three-panel workflow.

### `./test/md_gen/test_cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update CLI tests only for intentional wrapper changes while preserving default behavior assertions.
  - [ ] Add coverage for callback-compatible generation entrypoint if it is exposed from `foundation.py`.
- **Logic Modifications Required:**
  - [ ] Verify existing CLI parsing, verbose dump ordering, output creation, and batch persistence remain compatible.

### `./test/md_gen/test_page_processor.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add or update unit coverage for page-level progress behavior around PDF pages and standalone images.
- **Logic Modifications Required:**
  - [ ] Verify Markdown progress increments per PDF page and per image, not only per source file.
  - [ ] Verify current item data identifies the parent source document and PDF page number when applicable.

### `./test/md_mrg/test_mrg_plan.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add coverage for planning progress callbacks and active comparison pair payloads.
- **Logic Modifications Required:**
  - [ ] Verify comparison total is `max(n - 1, 0)`.
  - [ ] Verify zero-image and one-image planning cases emit deterministic completion and avoid division-by-zero.
  - [ ] Verify PDF document records are counted for UI state but not included in comparison progress.
  - [ ] Verify final image group count is derived from image groups in `batch_mrg.json`.

### `./test/webapp_tests/test_workflow_api.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Extend API tests from discovery/preview coverage to workflow state, OCR start, and SSE/snapshot behavior.
  - [ ] Add dependency injection or monkeypatch points for mocked generation and planning functions.
- **Logic Modifications Required:**
  - [ ] Verify OCR remains unavailable before successful non-empty discovery.
  - [ ] Verify OCR orchestration calls generation before planning.
  - [ ] Verify backend progress aggregation maps 0%-50% and 50%-100% correctly.
  - [ ] Verify failures in generation stop planning and mark OCR failed.
  - [ ] Verify failures in planning mark OCR failed after generation.
  - [ ] Verify final complete state has 100% progress and cleared active item/pair.

### `./src/webapp/frontend/package.json`
- **Type of Change:** Modify if frontend test tooling is not already present
- **Structural Changes:**
  - [ ] Add or confirm a frontend test script and dependencies suitable for component/API behavior tests.
- **Logic Modifications Required:**
  - [ ] Ensure frontend tests can mock SSE/EventSource and backend API responses.

### `./src/webapp/frontend/src/components/WorkflowPanel` test file
- **Type of Change:** Create if frontend test structure does not already exist
- **Structural Changes:**
  - [ ] Add component tests for discovery-enabled OCR, SSE state updates, count rendering, active document highlighting, active comparison highlighting, and OCR failure messages.
- **Logic Modifications Required:**
  - [ ] Mock discovery, OCR start, workflow snapshot, and SSE update paths.
  - [ ] Keep Merge and Rename placeholder behavior unchanged unless existing workflow rules require enabling changes after OCR completion.

## 3. Boundary & Edge Case Analysis
*Detail how system boundaries, errors, and edge cases will be handled structurally.*
- **Error Handling:** Configuration load/save failures remain HTTP 500 responses as today. Invalid source/output settings should return validation errors for the OCR start endpoint or transition workflow state to failed with an error message. `md_gen` configuration/gateway/runtime failures must stop the OCR workflow before planning. Missing, unreadable, or invalid `batch.json` after generation must be treated as OCR failure. `md_mrg` planner failures must mark OCR failed and preserve the fact that generation ran, but not mark OCR complete. SSE connections should emit the latest available state first and tolerate client disconnects without stopping the OCR run.
- **Security & Permissions:** No authentication or RBAC changes are implied for the local-first webapp. File preview and processing must continue to resolve paths from configured source/output directories only. Existing preview traversal protections should remain. OCR start should not accept arbitrary per-request source paths that bypass saved settings. SSE must not expose file contents; state should include display names, IDs, paths only where already exposed by discovery, counts, and progress metadata.
- **Performance / Scale Impact:** OCR and language-model calls are long-running and potentially blocking. Backend orchestration must avoid blocking state streaming and unrelated requests; the analysis implies a background task/thread or equivalent orchestration boundary even though cancellation is out of scope. Progress callbacks should be lightweight and should not perform repeated full directory scans. PDF page counts may be needed up front for total OCR jobs, so repeated rasterization/page-count work should be avoided where practical. SSE fanout is small for the local app; in-memory state is acceptable for this iteration.
- **Concurrency Boundaries:** The workflow should define behavior for repeated OCR clicks while a run is already active. Structurally, only one local OCR run should be active at a time unless the backend later introduces run IDs. A second OCR start during a running state should either return the current state or reject with a clear conflict-style error. Starting discovery while OCR is running should be defined as invalid or should reset only when no run is active.
- **State Recovery:** Because long-term job history is out of scope, state can be in-memory for the running webapp process. Browser reloads recover from the snapshot endpoint while the process is alive. Backend restarts lose transient workflow state, but generated files on disk remain owned by the processing modules and should not be silently represented as a completed in-memory run unless a future recovery feature is added.
- **Zero Work Cases:** Discovery with no supported files must keep OCR unavailable. If a lower-level generation function is called with zero OCR jobs, it must emit deterministic complete or empty progress and avoid division-by-zero. Planning with zero or one image Markdown entry must compute zero comparisons, write a valid plan if planner rules allow, and let the backend map the planning portion to completion.
- **Data Contract Edges:** Markdown count must represent OCR jobs completed, not top-level source document count. A multi-page PDF therefore increments Markdown progress per page even if the current `batch.json` document metadata remains one PDF record. PDF document count comes from `batch.json` document records. Image group count comes from `batch_mrg.json` image group records and must not count appended PDF records as image groups.
- **CLI Compatibility:** Existing CLIs must remain usable without the webapp. Default stdout must remain compatible with current tests and user expectations. Structured progress is primarily an in-process callback contract; CLI machine-readable output is optional and must be opt-in if added.

## 4. Verification Checklist
*A concrete list of what needs to be verified during/after implementation to ensure the analysis was correct.*
- [ ] Verify `Start` discovery succeeds with supported files, stores discovery state, and enables `OCR` only when `metrics.total_count > 0`.
- [ ] Verify discovery failure or zero supported files leaves `OCR` unavailable and renders the appropriate message.
- [ ] Verify changing settings/source paths invalidates previous discovery-derived OCR availability.
- [ ] Verify the OCR backend endpoint invokes Markdown generation before merge planning and never parses human-readable CLI logs.
- [ ] Verify `md_gen` reports total OCR jobs as PDF page count plus standalone image count.
- [ ] Verify Markdown count increments once per completed PDF page or standalone image.
- [ ] Verify `md_gen` emits current source item and PDF page information sufficient to highlight the parent source document.
- [ ] Verify successful generation writes `batch.json` and failure stops before merge planning.
- [ ] Verify `md_mrg` reports comparison total as `max(n - 1, 0)` for image Markdown entries.
- [ ] Verify active comparison events identify both compared source documents.
- [ ] Verify PDF document count is populated from `batch.json` and does not contribute to merge-planning progress.
- [ ] Verify image group count is populated from `batch_mrg.json` after planning completes.
- [ ] Verify overall OCR progress maps generation to 0%-50% and planning to 50%-100%, including zero-job substages.
- [ ] Verify OCR completion sets progress to 100%, marks OCR complete, clears current item and active comparison pair, and enables later stages only according to existing workflow rules.
- [ ] Verify generation failure and planning failure both render failed OCR state and do not present partial outputs as a completed OCR stage.
- [ ] Verify the SSE endpoint sends the latest state immediately on connection and streams subsequent state changes.
- [ ] Verify the frontend recovers via snapshot state after reload or SSE interruption without restarting OCR.
- [ ] Verify the existing discovered document list highlights the current OCR document and both documents in the active comparison pair.
- [ ] Verify the frontend status text remains user-facing as `OCR` while allowing messages like current file processing or pair comparison.
- [ ] Verify Merge and Rename remain placeholders unless explicitly enabled by existing post-OCR workflow rules.
- [ ] Verify existing `md_gen` CLI tests and `md_mrg` CLI/plan tests continue to pass or are updated only for intentional compatible interface changes.
- [ ] Verify focused backend workflow tests cover two-stage order, progress aggregation, failure handling, final counts, and SSE/snapshot behavior.
- [ ] Verify focused frontend tests cover OCR start wiring, state rendering, count updates, active row highlighting, active pair highlighting, and failure messages.
---