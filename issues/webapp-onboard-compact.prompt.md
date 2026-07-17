> **Traceability Metadata**
> - [Analysis Reference](./webapp-onboard-compact.plan.analysis.md)
> - Plan Scope: webapp-onboard-compact
> - Source Sections: Analysis Sections 1 through 4

# Implementation Plan: webapp-onboard-compact

> **Core Objective:** Detailed step-by-step technical execution blueprint for implementing the requirements specified in the analysis.

## Phase 1: Establish the webapp package boundary and settings persistence contract

**Traceability:** Implements Analysis Section 1 (architectural boundary and settings-only flow), Analysis Section 2 (`pyproject.toml`, `src/webapp/backend/models.py`, `src/webapp/backend/settings_store.py`, `data/config/settings.json`, `data/config/settings-default.json`, `test/webapp/test_settings_store.py`), and Analysis Section 3 (atomic writes, text-only folder paths, no CLI coupling).

**Goal:** Add the backend package surface to the existing root Python project, define a dedicated webapp settings schema, and centralize safe file-based persistence without reusing the CLI config loader.

### Steps
1. **[Analysis Section 1, Analysis Section 2: `pyproject.toml`]** Update the root Python manifest instead of creating a nested backend manifest. Add backend runtime dependencies needed for FastAPI and validation, and extend the wheel package list so the `src/webapp` package tree is installed from the same top-level project. Do not add `src/webapp/backend/pyproject.toml`; if such a file appears during implementation, remove it.
2. **[Analysis Section 1, Analysis Section 2: `src/webapp/backend/models.py`, Analysis Section 3]** Create a webapp-specific Pydantic schema that mirrors the persisted JSON contract and remains independent from `src/common/config.py`. Model the current top-level metadata and sections already present in `settings.json`, plus the new `source_folder` and `output_folder` string fields. Use URL-aware validation for model endpoints and numeric validation for timeout/retry fields, but keep the folder fields as plain strings with no existence checks.
3. **[Analysis Section 2: `data/config/settings.json`, `data/config/settings-default.json`, Analysis Section 3]** Extend both JSON files with `source_folder` and `output_folder` at the persisted top level, preserving the existing `ocr_model`, `language_model`, `md_gen`, and `md_mrg` sections unchanged apart from the new sibling keys. Keep bootstrap defaults aligned with the saved-file schema.
4. **[Analysis Section 2: `src/webapp/backend/settings_store.py`, Analysis Section 3]** Implement a dedicated settings store module with explicit constants for `data/config/settings.json` and `data/config/settings-default.json`, plus `load_settings(...)` and `save_settings(...)` helpers that accept optional paths for tests. `load_settings(...)` should bootstrap the working file from defaults when missing, parse JSON, validate into the webapp schema, and surface file/JSON failures as backend-facing exceptions rather than silent fallbacks.
5. **[Analysis Section 3, Analysis Section 4]** Make `save_settings(...)` perform atomic persistence in the same directory as the target file: serialize validated settings to JSON, write to a temporary sibling file, flush and fsync the temporary file handle, then replace the target with a single rename/replace operation. Return the validated saved payload so API callers can respond with the normalized document.
6. **[Analysis Section 2: `test/webapp/test_settings_store.py`, Analysis Section 4]** Add focused store tests that use temporary directories and monkeypatched file paths to verify bootstrap behavior, schema validation, plain-string folder round-tripping, and atomic replacement semantics without touching the real `data/config` files.

### Signature Sketch
```python
# src/webapp/backend/models.py
class ModelEndpointSettings(BaseModel):
    endpoint: AnyHttpUrl
    model: str
    timeout_seconds: PositiveFloat
    max_retries: NonNegativeInt

class AppSettings(BaseModel):
    app_name: str
    version: str
    source_folder: str
    output_folder: str
    ocr_model: ModelEndpointSettings
    language_model: ModelEndpointSettings
    md_gen: MdGenSettings
    md_mrg: MdMrgSettings
```

```python
# src/webapp/backend/settings_store.py
def load_settings(
    settings_path: Path = SETTINGS_FILE,
    defaults_path: Path = DEFAULT_SETTINGS_FILE,
) -> AppSettings: ...

def save_settings(
    payload: AppSettings,
    settings_path: Path = SETTINGS_FILE,
) -> AppSettings: ...
```

### Exit Criterion
- The root `pyproject.toml` is the only Python manifest involved, the persisted settings schema includes `source_folder` and `output_folder`, and the store can bootstrap, validate, and atomically rewrite settings without depending on `md_gen` or `md_mrg` config loaders.

### Validation Command
```bash
uv run pytest test/webapp/test_settings_store.py -q
```

## Phase 2: Expose the FastAPI settings API with a testable app factory

**Traceability:** Implements Analysis Section 1 (browser -> API -> settings file flow), Analysis Section 2 (`src/webapp/backend/app.py`, `test/webapp/test_settings_api.py`), Analysis Section 3 (422 validation, local-dev CORS, no workflow execution), and Analysis Section 4 (health/settings endpoint verification).

**Goal:** Build a minimal FastAPI application that exposes the required endpoints, validates request bodies with the webapp schema, and keeps all file access behind the settings store.

### Steps
1. **[Analysis Section 2: `src/webapp/backend/app.py`, Analysis Section 3]** Implement `create_app(...) -> FastAPI` and a module-level `app = create_app()` so production startup and tests can share the same route registration logic. Accept optional injected paths and allowed origins in the factory so tests can isolate filesystem state and assert CORS behavior deterministically.
2. **[Analysis Section 2: `src/webapp/backend/app.py`, Analysis Section 4]** Register `GET /health` returning exactly `{"status": "ok"}` and nothing workflow-related. Keep this endpoint dependency-free so it remains a pure startup probe.
3. **[Analysis Section 1, Analysis Section 2: `src/webapp/backend/app.py`, Analysis Section 4]** Register `GET /api/settings` so it calls `load_settings(...)`, returns the full validated JSON payload, and does not reshape or omit existing sections from the shared settings document.
4. **[Analysis Section 1, Analysis Section 2: `src/webapp/backend/app.py`, Analysis Section 3]** Register `PUT /api/settings` with the Pydantic request model as the request body. Let schema-invalid payloads, including malformed endpoint URLs, fail naturally as HTTP 422, and route validated payloads through `save_settings(...)` for atomic persistence.
5. **[Analysis Section 3, Analysis Section 4]** Add CORS middleware for local development origins used by the Vite frontend, covering both `localhost` and `127.0.0.1` on the selected dev port. Keep the allow-list narrow to frontend dev usage and avoid broad wildcard configuration.
6. **[Analysis Section 3, Analysis Section 4]** Convert store-level read/write failures into HTTP 500 responses with concise diagnostic messages, but do not swallow them or replace them with synthetic defaults. Keep the backend strictly limited to settings I/O; do not call `md_gen`, `md_mrg`, or `common.gateway` from the webapp API.
7. **[Analysis Section 2: `test/webapp/test_settings_api.py`, Analysis Section 4]** Add API tests with `fastapi.testclient.TestClient` against `create_app(...)`, using temporary settings/default files to verify `GET /health`, `GET /api/settings`, successful `PUT /api/settings`, HTTP 422 on invalid endpoint URLs, and atomic write behavior visible through the updated file contents.

### Signature Sketch
```python
# src/webapp/backend/app.py
def create_app(
    settings_path: Path = SETTINGS_FILE,
    defaults_path: Path = DEFAULT_SETTINGS_FILE,
    allowed_origins: Sequence[str] | None = None,
) -> FastAPI: ...
```

### Pseudocode
```text
app = FastAPI()
add_cors(app, allowed_origins or default_local_dev_origins)

GET /health:
  return {"status": "ok"}

GET /api/settings:
  return load_settings(settings_path, defaults_path).model_dump(mode="json")

PUT /api/settings:
  saved = save_settings(payload, settings_path)
  return saved.model_dump(mode="json")
```

### Exit Criterion
- The backend starts through a single FastAPI app object, exposes only the required endpoints, returns 422 for schema-invalid settings payloads, and keeps all persistence inside the dedicated settings store.

### Validation Command
```bash
uv run pytest test/webapp/test_settings_api.py -q
```

## Phase 3: Scaffold the frontend build and render the static workflow shell

**Traceability:** Implements Analysis Section 2 (`src/webapp/frontend/package.json`, `index.html`, `vite.config.ts`, `tailwind.config.ts`, `postcss.config.js`, `tsconfig.json`, `src/main.tsx`, `src/App.tsx`, `src/components/WorkspaceShell.tsx`, `src/styles.css`), Analysis Section 3 (fixed theme, no direct file reads), and Analysis Section 4 (frontend startup, workflow shell, sidebar behavior).

**Goal:** Create the React + Vite + Tailwind frontend foundation, render the required single-window shell, and lock the UI into the required dark visual direction.

### Steps
1. **[Analysis Section 2: `src/webapp/frontend/package.json`, `tsconfig.json`, `vite.config.ts`, `postcss.config.js`, `tailwind.config.ts`]** Create the frontend toolchain files with a minimal React + TypeScript + Vite setup plus Tailwind/PostCSS integration. Define scripts for local development and production build, and configure the Vite dev server to proxy `/api` and `/health` requests to the backend origin used during local development.
2. **[Analysis Section 2: `src/webapp/frontend/index.html`, `src/webapp/frontend/src/main.tsx`]** Create the Vite HTML shell and bootstrap entrypoint so the React application owns the full page and mounts global styles exactly once.
3. **[Analysis Section 2: `src/webapp/frontend/src/App.tsx`, `src/webapp/frontend/src/components/WorkspaceShell.tsx`, Analysis Section 4]** Implement a top-level shell state model with two concerns only: active section (`workflow` or `settings`) and sidebar visibility. Keep this as a single-window screen with no route changes.
4. **[Analysis Section 2: `src/webapp/frontend/src/components/WorkspaceShell.tsx`, Analysis Section 4]** Render the five workflow placeholders in the exact order required by the locked request: `source list`, `source preview`, `batch_mrg.json` panel, `merge-document preview`, `output list`. Keep them explicitly labeled placeholder panels and do not add live data bindings for this phase.
5. **[Analysis Section 3, Analysis Section 4]** Make the left side panel collapsible without leaving the current screen, and switch the side-panel content when the active section changes between Workflow and Settings. Do not introduce React Router or any multi-page navigation.
6. **[Analysis Section 2: `src/webapp/frontend/src/styles.css`, `tailwind.config.ts`, Analysis Section 3]** Define the fixed dark palette and light blue accent tokens in the frontend theme and use them consistently across the shell, panels, buttons, and form framing. Do not add any theme toggle, alternate theme definitions, or color-mode switching logic.

### Exit Criterion
- The frontend installs and builds, the shell renders as a single-screen workspace, the five placeholder panels appear in the required order, and the sidebar can hide/show while preserving the current section.

### Validation Command
```bash
npm --prefix src/webapp/frontend run build
```

## Phase 4: Implement the Settings view and API-driven save flow

**Traceability:** Implements Analysis Section 1 (settings edit round-trip), Analysis Section 2 (`src/webapp/frontend/src/components/SettingsForm.tsx`, `src/webapp/frontend/src/App.tsx`, `src/webapp/frontend/src/components/WorkspaceShell.tsx`), Analysis Section 3 (inline validation, text-only folder fields, backend-only config access), and Analysis Section 4 (settings UI, success feedback, no picker controls).

**Goal:** Connect the Settings screen to the backend API, keep the workflow shell static, and surface save/load/error states inside the existing single-window layout.

### Steps
1. **[Analysis Section 2: `src/webapp/frontend/src/components/SettingsForm.tsx`, Analysis Section 4]** Create a dedicated `SettingsForm` component that fetches `GET /api/settings` on initial mount, stores the full payload in local component state, and renders editable controls for OCR endpoint/model/timeout/retries, language model endpoint/model/timeout/retries, `source_folder`, and `output_folder`.
2. **[Analysis Section 3, Analysis Section 4]** Keep `source_folder` and `output_folder` as plain text inputs only. Do not add browse buttons, file dialogs, path existence warnings, or automatic filesystem probing.
3. **[Analysis Section 1, Analysis Section 3, Analysis Section 4]** Implement form submission through `PUT /api/settings`, sending the complete settings document back to the backend so the shared JSON file continues to round-trip intact. Avoid partial update semantics in this phase.
4. **[Analysis Section 3, Analysis Section 4]** Handle backend validation errors by mapping HTTP 422 field errors into inline form feedback next to the affected controls. Keep non-validation failures as a compact general error banner.
5. **[Analysis Section 1, Analysis Section 4]** Show a transient success confirmation after a successful save and clear it on subsequent edits or failed submissions. Keep the workflow panels untouched by these interactions.
6. **[Analysis Section 3, Analysis Section 4]** Ensure the frontend never reads `data/config/settings.json` directly and never invokes workflow execution endpoints or placeholder actions. All settings state must originate from API responses.

### Pseudocode
```text
onMount:
  GET /api/settings
  set form state from returned payload

onSubmit:
  clear prior success/errors
  PUT /api/settings with full payload
  if 422:
    map validation details to field errors
  elif success:
    show transient saved state
  else:
    show general error
```

### Exit Criterion
- The Settings screen loads current values from the backend, saves valid edits back to `data/config/settings.json`, shows inline 422 feedback for invalid endpoints, and keeps folder fields as text-only inputs.

### Validation Command
```bash
npm --prefix src/webapp/frontend run build
```

## Phase 5: Documentation and delivery verification

**Traceability:** Implements Analysis Section 2 (`src/webapp/README.md`), Analysis Section 4 (verification checklist), and the locked startup/documentation constraints from the request.

**Goal:** Document how to run the scaffold locally and close the implementation with the smallest verification set that proves the onboard matches scope.

### Steps
1. **[Analysis Section 2: `src/webapp/README.md`, Analysis Section 4]** Create `src/webapp/README.md` with the backend and frontend startup commands, the `src/webapp/backend` and `src/webapp/frontend` folder roles, and an explicit note that this phase provides a shell plus Settings editor only.
2. **[Analysis Section 4]** Document the backend startup command against the root Python project, for example `uv run uvicorn webapp.backend.app:app --reload --port 8000`, and document the frontend startup command from the frontend folder or via npm prefix, keeping the two-process local-dev model explicit.
3. **[Analysis Section 4]** Run the focused backend tests, run the frontend production build, and perform one manual smoke pass: backend health endpoint, settings load/save, workflow shell render, sidebar toggle, Workflow/Settings section switch, and absence of theme toggle or folder picker controls.
4. **[Analysis Section 4]** Confirm the finished implementation remains isolated from `md_gen` and `md_mrg` execution paths and that the backend OpenAPI docs are available at `/docs` once the server is running.

### Exit Criterion
- The local startup instructions are accurate, focused tests pass, the frontend build succeeds, and the manual smoke pass closes every item in the analysis verification checklist.

### Validation Command
```bash
uv run pytest test/webapp -q
npm --prefix src/webapp/frontend run build
```

## Final Delivery Gate

**Traceability:** Completes Analysis Section 4 end-to-end verification.

### Steps
1. **[Analysis Section 4]** Run the backend-focused suite first: `uv run pytest test/webapp/test_settings_store.py test/webapp/test_settings_api.py -q`.
2. **[Analysis Section 4]** Run the frontend build second: `npm --prefix src/webapp/frontend run build`.
3. **[Analysis Section 4]** If both automated checks pass, start the backend and frontend from the documented commands and manually verify the shell/order/sidebar/settings behaviors from the analysis checklist.
4. **[Analysis Section 4]** Do not expand scope into workflow execution, previews, auth, database work, or folder-picker UX while closing this issue.

### Exit Criterion
- Every requirement in the analysis has a direct implementation path, a concrete validation step, and no scope creep into deferred workflow features.

### Validation Command
```bash
uv run pytest test/webapp -q
npm --prefix src/webapp/frontend run build
```