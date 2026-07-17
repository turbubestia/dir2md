# Implementation Analysis: webapp-onboard-compact

## 1. Architectural Impact & Data Flow
*High-level overview of how data flows through the system for this feature. Identify any new patterns or structural additions.*
- **Affected Subsystems:** New webapp backend under `src/webapp/backend/`, new webapp frontend under `src/webapp/frontend/`, persisted config files in `data/config/`, local-dev documentation, and focused backend/API tests.
- **Data Flow Changes:** Browser UI loads the React shell -> Settings view requests `GET /api/settings` -> backend reads `data/config/settings.json`, validates it with a webapp-specific schema, and returns the full JSON payload -> user edits fields in the form -> frontend submits `PUT /api/settings` -> backend validates the request, returns `422` for invalid URLs or schema violations, and otherwise writes the updated JSON atomically back to `data/config/settings.json` -> success state is surfaced transiently in the UI. The workflow shell itself remains static placeholder layout in this phase, with no `md_gen` or `md_mrg` execution path.
- **Structural Shift:** Introduce a dedicated webapp boundary instead of reusing the CLI pipeline configuration path. The backend becomes the only reader/writer of settings for the browser UI, while the frontend remains config-agnostic and stateful only through API responses. Packaging should follow a single top-level Python project model: the root `pyproject.toml` remains the authoritative Python manifest, and the webapp backend is added to that project rather than becoming a separate nested Python distribution.

## 2. Component & File Impact Map
*Identify the exact files that must be created, modified, or deleted, and what structural changes they require.*

### `./src/webapp/README.md`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Document the two local startup commands for backend and frontend.
  - [ ] Document the backend/frontend folder layout under `src/webapp/`.
- **Logic Modifications Required:**
  - [ ] Clarify that the webapp is a shell plus settings editor only in this phase.

### `./pyproject.toml`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Extend the single top-level Python manifest to include the backend webapp module in the project package set.
  - [ ] Add any backend runtime dependencies required for FastAPI, request validation, and settings-file persistence.
- **Logic Modifications Required:**
  - [ ] Keep the webapp backend integrated into the root Python environment rather than creating a separate nested Python project.

### `./src/webapp/backend/pyproject.toml`
- **Type of Change:** Delete
- **Structural Changes:**
  - [ ] Do not introduce a second Python project manifest under the backend folder.
- **Logic Modifications Required:**
  - [ ] Avoid a split packaging hierarchy that would duplicate dependency resolution or create two independent Python environments.

### `./src/webapp/backend/app.py`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Host the FastAPI application object and the route registration surface.
  - [ ] Expose `GET /health`, `GET /api/settings`, and `PUT /api/settings`.
- **Logic Modifications Required:**
  - [ ] Wire request validation, CORS for local dev ports, and the atomic settings write flow.
  - [ ] Keep this app isolated from `md_gen` and `md_mrg` execution paths.

### `./src/webapp/backend/models.py`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Define the Pydantic schema for the persisted settings payload.
  - [ ] Include model sections, source/output folder strings, and any metadata fields that must round-trip through JSON.
- **Logic Modifications Required:**
  - [ ] Encode the validation rules that produce HTTP `422` for malformed endpoints or invalid request bodies.

### `./src/webapp/backend/settings_store.py`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Centralize reading from and writing to `data/config/settings.json`.
  - [ ] Preserve atomic persistence semantics so partial writes cannot corrupt the settings file.
- **Logic Modifications Required:**
  - [ ] Load from `settings-default.json` when bootstrapping a missing settings file.
  - [ ] Persist `source_folder` and `output_folder` as plain strings without directory-existence enforcement.

### `./src/webapp/frontend/package.json`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Define the React, Vite, and Tailwind application manifest.
  - [ ] Provide the local dev script surface for the frontend startup command.
- **Logic Modifications Required:**
  - [ ] Include the dependencies required for the fixed dark UI shell and API-driven settings form.

### `./src/webapp/frontend/index.html`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Provide the root HTML shell for Vite.
- **Logic Modifications Required:**
  - [ ] Keep the document minimal so the React app controls the entire screen layout.

### `./src/webapp/frontend/vite.config.ts`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Define the frontend dev-server/build configuration.
- **Logic Modifications Required:**
  - [ ] Point the frontend at the backend API origin expected during local development.

### `./src/webapp/frontend/tailwind.config.ts`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Define the design tokens and content paths for the frontend build.
- **Logic Modifications Required:**
  - [ ] Lock the theme direction to the required dark styling with light blue accents.

### `./src/webapp/frontend/postcss.config.js`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Provide the Tailwind PostCSS integration surface.
- **Logic Modifications Required:**
  - [ ] Keep the styling pipeline minimal and framework-appropriate.

### `./src/webapp/frontend/tsconfig.json`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Define the TypeScript compiler baseline for the frontend source tree.
- **Logic Modifications Required:**
  - [ ] Enforce a predictable React/Vite TypeScript setup.

### `./src/webapp/frontend/src/main.tsx`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Bootstrap the React application into the Vite root element.
- **Logic Modifications Required:**
  - [ ] Mount the application shell and global styling once at startup.

### `./src/webapp/frontend/src/App.tsx`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Own the single-window shell composition, left-panel toggle state, and Workflow/Settings section switching.
  - [ ] Render the five horizontal placeholder panels in the required order.
- **Logic Modifications Required:**
  - [ ] Keep the workflow panels static placeholders and route all Settings interaction through the backend API.

### `./src/webapp/frontend/src/components/SettingsForm.tsx`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Isolate the Settings view form fields and save interaction.
- **Logic Modifications Required:**
  - [ ] Load current values from the API, render inline validation feedback, and show a transient success state after saves.

### `./src/webapp/frontend/src/components/WorkspaceShell.tsx`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Encapsulate the collapsible navigation/sidebar and the workflow/settings section switch.
- **Logic Modifications Required:**
  - [ ] Keep the sidebar content synchronized with the active section while preserving the same screen.

### `./src/webapp/frontend/src/styles.css`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Provide the base visual system for the app shell.
- **Logic Modifications Required:**
  - [ ] Enforce the dark palette, light blue accents, and layout framing for the placeholder panes.

### `./data/config/settings.json`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add persisted `source_folder` and `output_folder` keys to the existing settings document.
  - [ ] Keep the current OCR and language model sections intact so the webapp writes the same shared file used by the rest of the project.
- **Logic Modifications Required:**
  - [ ] Preserve valid JSON structure for round-tripping through the backend API.

### `./data/config/settings-default.json`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Mirror the settings-file shape change so a missing settings file can be bootstrapped with the new folder fields.
- **Logic Modifications Required:**
  - [ ] Keep bootstrap defaults aligned with the persisted file schema.

### `./test/webapp/test_settings_api.py`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Add backend API coverage for `GET /health`, `GET /api/settings`, and `PUT /api/settings`.
- **Logic Modifications Required:**
  - [ ] Verify success, `422` validation behavior, and atomic write expectations.

### `./test/webapp/test_settings_store.py`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Add config-store coverage for JSON read/write and bootstrap behavior.
- **Logic Modifications Required:**
  - [ ] Verify folder paths round-trip as plain strings and persistence remains file-based only.

## 3. Boundary & Edge Case Analysis
*Detail how system boundaries, errors, and edge cases will be handled structurally.*
- **Error Handling:** Invalid endpoint URLs or malformed settings payloads must fail at the API boundary with `422` and field-level feedback in the frontend. File read/write failures should surface as backend errors rather than silent fallback behavior. Atomic writes are required so the settings file cannot be partially truncated on crash or interruption.
- **Security & Permissions:** This phase introduces no authentication, authorization, or database boundary. The only external boundary is local browser-to-backend CORS, which must allow the dev frontend origin while keeping the API focused on settings-only operations.
- **Performance / Scale Impact:** The workload is bounded to one JSON file and a small React UI, so runtime cost is negligible. The atomic-write and validation steps are intentionally more important than throughput. Long-running job execution, progress tracking, and previews remain out of scope and should not be introduced indirectly.
- **Boundary Rules to Preserve:** Folder values are text-only and must not require the target directories to exist. The frontend must never read `settings.json` directly. The webapp shell must not trigger `md_gen` or `md_mrg` behavior in this phase. The layout theme must remain fixed with no theme toggle or alternate theme selector.

## 4. Verification Checklist
*A concrete list of what needs to be verified during/after implementation to ensure the analysis was correct.*
- [ ] Verify the backend starts from the documented command and exposes `GET /health` with `{"status": "ok"}`.
- [ ] Verify `GET /api/settings` returns the full persisted JSON structure, including `source_folder` and `output_folder`.
- [ ] Verify `PUT /api/settings` updates `data/config/settings.json` atomically and preserves valid JSON.
- [ ] Verify invalid endpoint input returns HTTP `422` and the frontend shows inline validation feedback.
- [ ] Verify the frontend loads from the documented command and renders the workflow shell without startup errors.
- [ ] Verify the five horizontal workflow panels appear in the required order.
- [ ] Verify the left panel hides and shows without navigation loss.
- [ ] Verify switching between Workflow and Settings updates the sidebar content.
- [ ] Verify the Settings screen uses the fixed dark theme with light blue accents and no theme toggle exists.
- [ ] Verify source and output folder fields are plain text inputs and no browse/picker control appears.
- [ ] Verify the backend CORS configuration supports local frontend development.
- [ ] Verify the backend and frontend remain isolated from `md_gen` and `md_mrg` execution paths in this phase.