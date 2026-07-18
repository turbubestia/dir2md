# Implementation Plan: webapp-workflow-panel-redesign

> **Core Objective:** Detailed step-by-step technical execution blueprint for implementing the requirements specified in the analysis.

## Traceability

- **Analysis Reference:** [Analysis Reference](./webapp-workflow-panel-redesign.plan.analysis.md)
- **Issue Name:** `webapp-workflow-panel-redesign`
- **Scope Guard:** Implement only the workflow Start discovery API, local file preview boundary, frontend workflow panel, tests, and documentation described here. Do not implement real OCR, merge, rename, `batch_merge.json` persistence, or new PDF rendering dependencies.

## Phase 1: Backend Contract Models

Implementing requirements from Analysis Sections 1, 2 `src/webapp/backend/models.py`, and 3 Error Handling/Security.

### Steps

1. Add workflow response schemas to `src/webapp/backend/models.py` while preserving the existing settings schemas unchanged. Use Pydantic v2 models and `Literal` types that align with `md_gen.discovery.SourceType`.
2. Define constrained status and severity types for the API contract:
   - `SourceFileType = Literal["pdf", "image"]`
   - `FolderStatusKind = Literal["not_configured", "missing", "not_directory", "inaccessible", "empty", "ready"]`
   - `WorkflowMessageSeverity = Literal["info", "success", "warning", "error"]`
3. Add models with snake_case field names so the frontend can consume responses without reshaping:
   - `WorkflowStatusMessage(severity, code, message)`
   - `FolderStatus(path, status, message, item_count: int | None = None)`
   - `WorkflowSourceFile(id, display_name, absolute_path, extension, size_bytes, source_type, order_index, preview_url: str | None = None)`
   - `WorkflowMetrics(pdf_count, image_count, total_count)`
   - `WorkflowDiscoveryResponse(ok, source_status, output_status, metrics, items, messages)`
4. Keep the schema capable of representing `ok=True` with `total_count=0` for unsupported-only or empty source folders, and `ok=False` for invalid configuration or filesystem failures.

### Exit Criterion

The backend has typed workflow response models that distinguish hard discovery failures from successful zero-item discovery, and no existing settings API model names or fields are changed.

### Validation Command

```powershell
uv run pytest test/webapp_tests/test_settings_api.py
```

## Phase 2: Backend Workflow Service

Implementing requirements from Analysis Sections 1, 2 `src/webapp/backend/workflow.py`, 2 `src/md_gen/discovery.py`, and 3 Boundary/Security/Performance.

### Steps

1. Create `src/webapp/backend/workflow.py` as the service boundary for Start discovery and preview validation. Route handlers must delegate to this module instead of doing filesystem traversal inline.
2. Import and use existing discovery behavior rather than duplicating extension lists or sorting:
   - `from md_gen.discovery import build_work_items`
   - `from common.config import AppConfig, PathSettings, PromptSettings, LlamaModelSettings, ImageSettings, RuntimeSettings, MdGenSettings, MdMrgSettings`
3. Add a lightweight settings-to-config adapter that builds the minimum valid `AppConfig` required by `build_work_items`. Do not call `common.config.build_config_from_args`, because it creates output directories and reads prompt files as CLI runtime setup. Construct dataclasses directly from the already-loaded `AppSettings`.
4. Recommended service signatures:
   ```python
   class WorkflowServiceError(Exception): ...

   def discover_start(settings: AppSettings) -> WorkflowDiscoveryResponse: ...

   def resolve_preview_path(settings: AppSettings, file_id: str) -> Path: ...
   ```
5. Validate `settings.source_folder` before calling discovery:
   - Empty string -> `ok=False`, `source_status.status="not_configured"`.
   - Missing path -> `ok=False`, `status="missing"`.
   - Existing non-directory -> `ok=False`, `status="not_directory"`.
   - `OSError`/permission failure during resolve or iteration -> `ok=False`, `status="inaccessible"`.
6. Inspect `settings.output_folder` only for reporting. Do not create folders or write artifacts. Return `not_configured`, `missing`, `not_directory`, `inaccessible`, `empty`, or `ready` with `item_count` when available.
7. For valid source folders, call `build_work_items(app_config)` and convert returned `FileItem` values into `WorkflowSourceFile` records. Count PDFs/images from `item.source_type`, not from extensions.
8. Create stable preview ids without allowing arbitrary filesystem reads. Use URL-safe base64 of the resolved source-relative path or another reversible relative identifier. In `resolve_preview_path`, decode the id, join it under the resolved configured source folder, resolve the result, reject path traversal, require the file to exist, require `is_file()`, and require the file to be present in the current `build_work_items` result.
9. Populate `preview_url` only for `source_type="image"`, using `/api/workflow/source-preview/{id}`. Leave PDFs metadata-only.

### Exit Criterion

`workflow.py` can produce discovery responses and validate preview paths through current settings without side effects, without duplicate supported-extension rules, and without exposing arbitrary local files.

### Validation Command

```powershell
uv run pytest test/webapp_tests/test_workflow_api.py
```

## Phase 3: Backend Routes and API Error Mapping

Implementing requirements from Analysis Sections 1, 2 `src/webapp/backend/app.py`, and 3 Error Handling/Security.

### Steps

1. Modify `src/webapp/backend/app.py` inside `create_app` to add:
   - `POST /api/workflow/start` returning `WorkflowDiscoveryResponse`
   - `GET /api/workflow/source-preview/{file_id}` returning a file response for validated image previews
2. Keep `/health`, `GET /api/settings`, and `PUT /api/settings` behavior unchanged.
3. For `POST /api/workflow/start`, call `load_settings(settings_path, defaults_path)` first. Convert `SettingsStoreError` into `JSONResponse(status_code=500, content={"detail": str(exc)})` following the current settings route pattern.
4. Call `discover_start(settings)` and return its response model. Discovery validation failures should normally return HTTP 200 with `ok=False` and structured messages when the request is valid but configured folders are not usable. Reserve 500 for unexpected service exceptions.
5. For preview, load settings, call `resolve_preview_path(settings, file_id)`, and return `FileResponse(path)`. Convert rejected ids/out-of-source files/missing files to 404 or 400 with readable `detail`; do not return the file path on rejection.
6. Add imports only for the new models/service functions and FastAPI response types needed by the routes.

### Exit Criterion

The webapp exposes Start discovery and image preview endpoints through the existing application factory, while tests can still inject temporary settings/default paths.

### Validation Command

```powershell
uv run pytest test/webapp_tests
```

## Phase 4: Backend Workflow API Tests

Implementing requirements from Analysis Sections 2 `test/webapp_tests/test_workflow_api.py`, 3 Boundary & Edge Case Analysis, and 4 Verification Checklist.

### Steps

1. Create `test/webapp_tests/test_workflow_api.py` instead of expanding settings tests heavily. Reuse the `create_app(settings_path=..., defaults_path=..., allowed_origins=[...])` injection pattern from `test_settings_api.py`.
2. Add small fixture helpers that write a valid settings JSON document with configurable `source_folder` and `output_folder`. Use `tmp_path` directories and tiny placeholder files; discovery only needs filenames and extensions.
3. Cover successful discovery:
   - Source contains PDF, PNG/JPG/JPEG, unsupported file, and subdirectory.
   - `POST /api/workflow/start` returns status 200, `ok=True`, ordered items matching `md_gen.discovery` natural ordering, and correct `pdf_count`/`image_count`/`total_count`.
   - Image items have `preview_url`; PDF items do not require a preview URL.
4. Cover zero-item source folders:
   - Empty source returns `ok=True`, `total_count=0`, warning/info message, and does not enable downstream semantics in the response.
   - Unsupported-only source returns `ok=True`, `total_count=0`, not a hard error.
5. Cover folder status cases: empty source setting, missing source, non-directory source, missing output, empty output, and non-empty output.
6. Cover preview route security:
   - Valid image preview returns 200 and an image-compatible content type or file bytes.
   - PDF preview id, unsupported file id, path traversal id, outside-source id, and missing file return rejection without leaking arbitrary file content.
7. Assert Start discovery does not create the configured missing output folder and does not write files into existing output folders.

### Exit Criterion

Workflow API tests prove discovery, folder statuses, ordering, preview validation, and no-output-write behavior independently of the frontend.

### Validation Command

```powershell
uv run pytest test/webapp_tests
```

## Phase 5: Frontend Types and API Client

Implementing requirements from Analysis Sections 1, 2 `src/webapp/frontend/src/types.ts`, 2 `src/webapp/frontend/src/api.ts`, and 3 Boundary Constraints.

### Steps

1. Extend `src/webapp/frontend/src/types.ts` with interfaces matching the backend response model exactly in snake_case:
   - `WorkflowStageKey = 'start' | 'ocr' | 'merge' | 'rename'`
   - `WorkflowStageState = 'unavailable' | 'enabled' | 'running' | 'complete' | 'selected'`
   - `WorkflowStatusSeverity = 'info' | 'success' | 'warning' | 'error'`
   - `FolderStatus`, `WorkflowStatusMessage`, `WorkflowSourceFile`, `WorkflowMetrics`, `WorkflowDiscoveryResponse`
   - Placeholder display types for OCR tree rows, merge rows, and rename rows.
2. Extend `src/webapp/frontend/src/api.ts` without changing existing settings functions:
   - `export async function startWorkflowDiscovery(): Promise<WorkflowDiscoveryResponse>` calling `POST /api/workflow/start`.
   - `export function buildSourcePreviewUrl(item: WorkflowSourceFile): string | undefined` that returns `item.preview_url ?? undefined`.
3. Follow the existing error style: parse `{detail}` on non-OK responses and throw `Error(detail || "...")`.
4. Do not add API calls for OCR, Merge, or Rename.

### Exit Criterion

Frontend code has typed access to discovery and preview URLs while existing settings API calls are untouched.

### Validation Command

```powershell
Push-Location src/webapp/frontend; npm run build; Pop-Location
```

## Phase 6: Workflow Panel Component

Implementing requirements from Analysis Sections 1, 2 `WorkflowPanel.tsx`, 2 `WorkspaceShell.tsx`, and 3 Performance/Module Boundary Constraints.

### Steps

1. Create `src/webapp/frontend/src/components/WorkflowPanel.tsx` as the owner of workflow state, API calls, selected stage, selected item, placeholder animation state, metrics, and status messages.
2. Use four stages only: Start, OCR, Merge, Rename. Render them as rounded rectangular buttons with state-dependent classes. Use semantic buttons and disabled/aria attributes where appropriate.
3. Implement Start behavior:
   - On click, set Start running and call `startWorkflowDiscovery()`.
   - Clear OCR/Merge/Rename placeholder state on every Start run.
   - Store returned items/metrics/messages/statuses.
   - Select the first item when available.
   - Mark Start complete when `response.ok` is true.
   - Enable OCR only when `response.ok` is true and `response.metrics.total_count > 0`.
4. Implement placeholder stages locally:
   - Clicking unavailable stages sets a warning status and makes no network call.
   - Clicking OCR after Start runs a short timer animation, marks OCR complete, enables Merge, and creates placeholder OCR tree rows from Start items.
   - Clicking Merge after OCR runs a short timer animation, marks Merge complete, enables Rename, and creates placeholder merge rows.
   - Clicking Rename after Merge runs a short timer animation and marks Rename complete with unavailable/future rename values.
5. Render the top workflow controls, animated connector/progress bar, metrics row, and status area. Metrics should show discovered PDF/image counts under Start and placeholder/unavailable values for downstream stages.
6. Render the three-panel workspace:
   - Left panel: Start source list, OCR placeholder tree, Merge placeholder list, or Rename placeholder list based on selected stage.
   - Middle panel: selected image preview via backend URL; selected PDF metadata fallback; placeholder metadata for simulated stages.
   - Right panel: markdown preview unavailable/empty for Start and clear placeholder content for simulated stages.
7. Handle long names/paths with truncation or wrapping classes and keep lists scrollable inside the panel.
8. Do not import or invoke any Python workflow code from the frontend, and do not persist workflow artifacts.
9. Modify `WorkspaceShell.tsx` to import and render `<WorkflowPanel />` in the Workflow section, preserving shell navigation, sidebar, toolbar, and Settings behavior.

### Exit Criterion

The Workflow view is a functional four-stage panel: real Start discovery, image preview through the backend, PDF metadata fallback, local-only downstream simulations, and reset behavior on Start rerun.

### Validation Command

```powershell
Push-Location src/webapp/frontend; npm run build; Pop-Location
```

## Phase 7: Styling and Responsive Layout

Implementing requirements from Analysis Sections 2 `src/webapp/frontend/src/styles.css`, 3 Performance, and 4 Visual Verification.

### Steps

1. Extend `src/webapp/frontend/src/styles.css` in the existing Tailwind `@layer components` style. Preserve the current dark shell palette and component conventions.
2. Add reusable classes for:
   - Stage buttons and state variants: unavailable, enabled, selected, running, complete.
   - Progress connector states.
   - Metric cells.
   - Status message severities.
   - Workflow list rows, selected rows, tree rows, and preview panels.
3. Ensure the main workflow content fills the shell area without expanding the page. Use `min-h-0`, `overflow-hidden`, and inner scroll containers where needed.
4. Add responsive behavior so the three panels become vertically stacked or horizontally scrollable on narrow screens without overlap.
5. Make filenames and paths robust with `break-words`, `truncate`, or constrained `min-w-0` usage.

### Exit Criterion

The workflow panel remains usable at desktop and narrow widths, and all visual states are distinguishable without breaking the existing settings UI.

### Validation Command

```powershell
Push-Location src/webapp/frontend; npm run build; Pop-Location
```

## Phase 8: Webapp Documentation

Implementing requirements from Analysis Sections 2 `src/webapp/README.md`, 3 Module Boundary Constraints, and 4 Verification Checklist.

### Steps

1. Update `src/webapp/README.md` scope language from five placeholder workflow panels to Start discovery plus simulated OCR/Merge/Rename stages.
2. Document the new routes:
   - `POST /api/workflow/start`
   - `GET /api/workflow/source-preview/{file_id}`
3. State explicitly that Start discovery reads configured folders, image preview streams validated local source files, PDF preview is metadata-only, and downstream stages are frontend-only simulations in this task.
4. Keep existing backend/frontend development commands current.

### Exit Criterion

The README accurately describes the implemented webapp behavior and does not imply real OCR, merge, rename, or PDF rendering support.

### Validation Command

```powershell
uv run pytest test/webapp_tests; Push-Location src/webapp/frontend; npm run build; Pop-Location
```

## Phase 9: Final Integrated Verification

Implementing requirements from Analysis Section 4 Verification Checklist.

### Steps

1. Run backend webapp tests and confirm settings regression plus workflow API coverage pass.
2. Run the frontend production build.
3. Optional manual smoke check when a browser is available:
   - Start backend: `uv run uvicorn webapp.backend.app:app --reload --port 8000`
   - Start frontend from `src/webapp/frontend`: `npm run dev`
   - Configure source/output folders in Settings, return to Workflow, click Start, select image/PDF items, and click OCR/Merge/Rename to confirm local-only progress.
4. Inspect `git diff` for accidental implementation scope creep: no real OCR/merge/rename invocation, no output artifact writes in Start, no unrelated refactors.

### Exit Criterion

All automated validation passes, the workflow behavior matches the analysis checklist, and remaining manual-only visual checks are clearly noted if not executed.

### Validation Command

```powershell
uv run pytest test/webapp_tests; Push-Location src/webapp/frontend; npm run build; Pop-Location
```

## Implementation Guardrails

- Every backend filesystem decision must remain inside `webapp.backend.workflow`; route handlers should stay thin.
- Discovery ordering/type classification must come from `md_gen.discovery.build_work_items`.
- Start discovery must not create output folders, write output files, run OCR, run merge, run rename, or persist workflow JSON.
- Preview delivery must validate against the current configured source folder and current discovered supported files before returning bytes.
- Existing settings API contracts and tests must remain valid.
- Frontend downstream stages are stateful visual simulations only; they must not call backend endpoints.
- Do not add frontend test infrastructure unless the project already adopts it during implementation; use `npm run build` and manual smoke checks otherwise.