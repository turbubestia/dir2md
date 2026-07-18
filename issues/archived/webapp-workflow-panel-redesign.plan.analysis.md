# Implementation Analysis: webapp-workflow-panel-redesign

## 1. Architectural Impact & Data Flow
*High-level overview of how data flows through the system for this feature. Identify any new patterns or structural additions.*
- **Affected Subsystems:** Frontend workflow UI, frontend API client/types, FastAPI backend routes, backend workflow/discovery service boundary, webapp settings store, `md_gen` discovery integration, backend and frontend tests, webapp documentation.
- **Data Flow Changes:**
  - User opens the existing webapp shell -> selects Workflow -> React renders the new four-stage workflow panel instead of the current five placeholder panels.
  - User clicks Start -> frontend calls a new workflow discovery API -> backend loads persisted webapp settings -> backend validates configured source and output folders -> backend adapts the configured source folder into the path-bearing config required by `md_gen.discovery` -> `md_gen.discovery` returns supported PDF/image work items -> backend adds folder status and preview-safe metadata -> frontend stores Start results, resets OCR/Merge/Rename state, updates metrics, enables OCR, and selects the Start stage list.
  - User selects a discovered Start item -> frontend renders image previews through a backend-served preview URL when the item is an image -> frontend renders PDF metadata fallback when the item is a PDF -> markdown preview remains empty/unavailable for Start.
  - User clicks OCR, Merge, or Rename after prerequisites are satisfied -> frontend runs a visual-only placeholder animation -> progress state advances locally -> stage metrics/list content switch to placeholder structures -> no OCR, merge, rename, JSON persistence, or Python processing is invoked.
  - User reruns Start -> frontend clears downstream placeholder state -> backend reruns discovery from current settings -> frontend rebuilds Start list/metrics and treats OCR as the only next available downstream stage after success.

## 2. Component & File Impact Map
*Identify the exact files that must be created, modified, or deleted, and what structural changes they require.*

### `./src/webapp/backend/app.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add a workflow Start discovery route under the existing `/api` route namespace.
  - [ ] Add a source file preview route or equivalent backend delivery boundary for discovered local files that the browser cannot access directly.
  - [ ] Wire the new route(s) through the `create_app` factory so tests can inject temporary settings/default paths.
  - [ ] Keep existing `/health`, `GET /api/settings`, and `PUT /api/settings` contracts unchanged.
- **Logic Modifications Required:**
  - [ ] Load current settings before discovery and translate settings-store failures into readable API errors.
  - [ ] Delegate discovery and folder validation to a backend workflow service instead of embedding filesystem traversal logic in route handlers.
  - [ ] Return clear error responses for missing, empty, inaccessible, or invalid configured folders.
  - [ ] Avoid calling `md_gen`, `md_mrg`, rename code, or any long-running workflow execution from the new route.

### `./src/webapp/backend/models.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add response models for workflow discovery results, discovered source file metadata, folder status, and workflow status messages.
  - [ ] Represent discovered file type as a constrained value matching `md_gen.discovery` source types: PDF or image.
  - [ ] Include metadata fields needed by the frontend list and preview panel, such as display name, absolute path or stable id, extension, size, and order index.
  - [ ] Include Start metrics in the response shape: PDF count and image count.
  - [ ] Include output folder status in the response shape without implying OCR or merge output has been generated.
- **Logic Modifications Required:**
  - [ ] Ensure response schema distinguishes successful discovery with zero supported files from hard failure.
  - [ ] Ensure preview identifiers or paths are structured so the backend can validate file access before serving preview content.

### `./src/webapp/backend/workflow.py`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Add a backend workflow service boundary for Start discovery and preview metadata preparation.
  - [ ] Add a settings-to-discovery adapter that supplies `md_gen.discovery` with the configured source directory without duplicating supported extension or ordering rules.
  - [ ] Add output folder status inspection for missing, inaccessible, empty, and non-empty output folders.
  - [ ] Add source folder validation for empty path, missing directory, non-directory path, inaccessible directory, and supported-file-empty states.
- **Logic Modifications Required:**
  - [ ] Call `md_gen.discovery.build_work_items` or the nearest existing discovery function so ordering and type classification remain centralized in `src/md_gen/discovery.py`.
  - [ ] Build frontend-safe response metadata from `FileItem` values returned by discovery.
  - [ ] Count PDFs and images from discovery output rather than rechecking extensions in the webapp layer.
  - [ ] Inspect output folder contents only for status reporting; do not create output folders or write workflow artifacts during Start discovery.
  - [ ] Normalize filesystem exceptions into explicit workflow discovery error states.

### `./src/md_gen/discovery.py`
- **Type of Change:** No direct feature change expected; potential compatibility review
- **Structural Changes:**
  - [ ] Preserve the existing public discovery functions and `FileItem` shape used by CLI workflows.
  - [ ] Confirm the supported extension set includes PDF plus common image extensions expected by the webapp.
- **Logic Modifications Required:**
  - [ ] Do not add webapp-specific response or preview logic here; keep this module focused on discovery and work-item normalization.
  - [ ] If filesystem edge cases surface during API tests, expose them through the backend service boundary rather than changing discovery into an API-aware component.

### `./src/webapp/frontend/src/components/WorkspaceShell.tsx`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace the current inline workflow placeholder panel layout with a dedicated workflow panel component.
  - [ ] Keep the existing shell, sidebar, Workflow/Settings navigation, toolbar, and Settings view behavior intact.
  - [ ] Ensure the Workflow section fills the available content area and supports responsive overflow without breaking the shell layout.
- **Logic Modifications Required:**
  - [ ] Delegate workflow state, API calls, metrics, progress rendering, and preview selection to the new workflow component.
  - [ ] Avoid introducing OCR, merge, or rename execution concerns into the shell component.

### `./src/webapp/frontend/src/components/WorkflowPanel.tsx`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Add a four-stage workflow progress control with Start, OCR, Merge, and Rename as rounded rectangular buttons.
  - [ ] Add stage state representation for unavailable, enabled, active/running, complete, and selected states.
  - [ ] Add an animated connector/progress bar that advances when Start completes and when visual placeholder stages complete.
  - [ ] Add a metrics row aligned under the four stage buttons.
  - [ ] Add a status message area below the workflow controls for success, empty-folder, unavailable-stage, placeholder-progress, and error messages.
  - [ ] Add the three-panel workspace: stage-dependent item list/tree, source preview, and markdown preview.
  - [ ] Add Start stage list rendering for discovered source files.
  - [ ] Add OCR placeholder tree rendering that anticipates document groups with image children and PDF leaf nodes.
  - [ ] Add Merge placeholder flat-list rendering.
  - [ ] Add Rename placeholder list rendering with future rename values represented as unavailable.
- **Logic Modifications Required:**
  - [ ] On Start click, call the new discovery API, reset OCR/Merge/Rename state, populate Start metrics/list, select the first discovered item when available, and enable OCR only after successful discovery.
  - [ ] On OCR, Merge, or Rename click, enforce prerequisite gating, run a timed frontend-only animation, update local completion state, and show status text that the stage is simulated for visual testing.
  - [ ] On unavailable step click, avoid backend calls and display a status message explaining that prerequisites are incomplete.
  - [ ] Render inline image previews through backend preview URLs and render PDF metadata fallback without adding a PDF rendering dependency.
  - [ ] Keep markdown preview empty or unavailable on Start; use placeholder or unavailable copy for unwired stages.
  - [ ] Ensure rerunning Start clears selected downstream placeholder data and metrics.

### `./src/webapp/frontend/src/api.ts`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add a typed API function for Start discovery.
  - [ ] Add a helper or URL builder for source file preview delivery if preview is exposed as a backend endpoint.
  - [ ] Preserve existing settings API functions and error-handling patterns.
- **Logic Modifications Required:**
  - [ ] Translate non-OK discovery responses into readable frontend errors.
  - [ ] Keep OCR, Merge, and Rename placeholder interactions local; do not add API calls for those stages in this task.

### `./src/webapp/frontend/src/types.ts`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add TypeScript interfaces for workflow stage keys, stage states, discovery response, source file metadata, folder status, workflow metrics, and status severity.
  - [ ] Add placeholder item/tree types for OCR, Merge, and Rename display states.
  - [ ] Keep existing settings interfaces unchanged.
- **Logic Modifications Required:**
  - [ ] Align frontend response types with backend Pydantic response models to avoid field-name reshaping in components.

### `./src/webapp/frontend/src/styles.css`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add reusable component classes or Tailwind layer entries for workflow stage buttons, progress connector states, metric cells, status message variants, list rows, tree rows, and preview panels.
  - [ ] Add responsive layout support for the three-panel workspace on narrow screens.
  - [ ] Preserve the existing dark shell palette and component conventions.
- **Logic Modifications Required:**
  - [ ] Ensure disabled, active, selected, completed, and running stage states are visually distinguishable.
  - [ ] Ensure long filenames and filesystem paths wrap or truncate without overlapping controls.

### `./src/webapp/README.md`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update the webapp scope description from workflow placeholders to Start discovery plus simulated downstream stages.
  - [ ] Document the new workflow API route and the fact that OCR, Merge, and Rename are frontend-only simulations for this task.
  - [ ] Note that PDF preview remains metadata-only unless a PDF rendering dependency is approved later.
- **Logic Modifications Required:**
  - [ ] Keep local development commands and settings API documentation current.

### `./test/webapp_tests/test_settings_api.py`
- **Type of Change:** Modify or split coverage into a new workflow API test file
- **Structural Changes:**
  - [ ] Add API tests for the discovery endpoint using injected temporary settings and filesystem fixtures.
  - [ ] Add tests for successful PDF/image discovery counts and ordered file metadata.
  - [ ] Add tests for empty source, missing source, missing output, empty output, and unsupported-only source folder statuses.
  - [ ] Add tests that the preview route rejects files outside the configured discovered/source boundary.
- **Logic Modifications Required:**
  - [ ] Ensure tests verify the endpoint uses `md_gen.discovery` behavior rather than duplicating a separate extension list in the webapp layer.
  - [ ] Ensure settings API tests continue to pass unchanged.

### `./test/webapp_tests/test_workflow_api.py`
- **Type of Change:** Create if workflow coverage is separated from settings API coverage
- **Structural Changes:**
  - [ ] Add focused FastAPI tests for workflow discovery and preview delivery.
  - [ ] Add fixtures for temporary source/output folders with PDF, image, unsupported, and directory entries.
- **Logic Modifications Required:**
  - [ ] Verify status codes and response bodies for success and failure edge cases.
  - [ ] Verify Start discovery has no output writes or downstream process side effects.

### `./src/webapp/frontend/src/components/WorkflowPanel.test.*` or equivalent frontend test location
- **Type of Change:** Optional Create, depending on the frontend test tooling available in the project
- **Structural Changes:**
  - [ ] Add component-level coverage for stage gating, Start success state, placeholder completion state, unavailable clicks, and source item selection if a frontend test runner is introduced.
- **Logic Modifications Required:**
  - [ ] Avoid adding frontend testing infrastructure solely for this task unless the project adopts it deliberately; otherwise validate with build and manual browser checks.

## 3. Boundary & Edge Case Analysis
*Detail how system boundaries, errors, and edge cases will be handled structurally.*
- **Error Handling:**
  - Settings load failures should return a readable API error and prevent Start from enabling downstream stages.
  - Empty `source_folder` or `output_folder` settings should be represented as configuration errors or warning statuses in the Start status area.
  - Missing source folder, non-directory source path, inaccessible source path, and discovery `OSError` cases should produce clear discovery failure responses.
  - Source folder with no supported PDF/image files should be a successful discovery response with zero counts plus a warning/status message, not an unhandled exception.
  - Missing, non-directory, inaccessible, or empty output folder should be reported as folder status; Start discovery should not create workflow output as a side effect.
  - Preview requests for files that no longer exist should show a readable preview error without invalidating the whole workflow UI.
  - OCR, Merge, and Rename disabled/prerequisite clicks should remain frontend-only and should not produce network errors.
- **Security & Permissions:**
  - The webapp is local-first and currently has no authentication; the new preview endpoint must still prevent arbitrary filesystem read-through by validating requested files against the configured source folder and supported/discovered file set.
  - API responses should avoid exposing more filesystem data than needed for the local UI; absolute paths may be displayed for metadata but should not become unchecked preview fetch inputs.
  - CORS behavior should remain constrained to the existing local development origins unless a deployment requirement changes it.
  - No database, RBAC, or user permission model is introduced by this task.
- **Performance / Scale Impact:**
  - Discovery is top-level source directory scanning only according to the current `md_gen.discovery` behavior, so large recursive traversal is not introduced.
  - The backend should return metadata for discovered files rather than embedding image bytes in the discovery response.
  - Image preview delivery should stream or serve the selected file on demand, not preload all images.
  - Placeholder animations must be timer/state based and must not poll backend services.
  - Long lists should remain scrollable within the left panel so large source folders do not expand the shell layout.
- **Module Boundary Constraints:**
  - Discovery rules remain centralized in `src/md_gen/discovery.py`.
  - Webapp backend may adapt settings and serialize discovery results, but it must not duplicate OCR or merge business logic.
  - Frontend may simulate OCR/Merge/Rename progress for visual validation, but it must not invoke `md_gen`, `md_mrg`, rename modules, or persist `batch_merge.json` in this task.
  - PDF rendering dependency adoption remains out of scope; PDF preview is metadata-only unless explicitly approved later.

## 4. Verification Checklist
*A concrete list of what needs to be verified during/after implementation to ensure the analysis was correct.*
- [ ] Verify `uv run pytest test/webapp_tests` covers settings API regression plus the new workflow discovery route.
- [ ] Verify successful Start discovery returns PDF/image metadata ordered consistently with `md_gen.discovery`.
- [ ] Verify Start metrics show discovered PDF and image counts after a successful discovery.
- [ ] Verify source folder with unsupported files only returns a no-supported-files status without enabling downstream stages as a hard failure.
- [ ] Verify missing or inaccessible configured folders return readable errors and do not enable OCR.
- [ ] Verify empty output folder status is returned and displayed without creating output artifacts.
- [ ] Verify selected image previews render inline through the backend preview boundary.
- [ ] Verify selected PDF previews show metadata fallback and no PDF rendering package is required.
- [ ] Verify Start rerun resets OCR, Merge, Rename completion state and leaves OCR as the next available stage after success.
- [ ] Verify OCR placeholder click after Start animates for a few seconds, marks OCR complete, enables Merge, and makes no backend OCR call.
- [ ] Verify Merge placeholder click after OCR animates, marks Merge complete, enables Rename, and makes no backend merge call.
- [ ] Verify Rename placeholder click after Merge animates and marks Rename complete without implying rename implementation exists.
- [ ] Verify unavailable stage clicks show a status message and do not call the backend.
- [ ] Verify the three-panel workspace switches list/tree/list content by selected stage and remains usable on narrow viewports.
- [ ] Verify `npm run build` from `src/webapp/frontend` passes after frontend changes.
- [ ] Verify the implemented workflow visually matches the row order and layout intent of `issues/workflow-panel.png`.
---