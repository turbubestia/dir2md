# Consolidated Requirements: Webapp Onboard
**Status:** LOCKED

## 1. Refinement Journey & Evolution
- **User Intent:** Establish an initial local-first web application foundation for dir2md, with a Python FastAPI backend and a TypeScript frontend, while keeping configuration persisted in `data/config/settings.json` and avoiding database/auth complexity.
- **Consolidation Summary:** Early drafts included broader workflow ambitions (plan/apply orchestration, previews, and `batch_mrg.json` interactions), but refinements narrowed the onboard to scaffold-only delivery. Iteration decisions finalized React + Vite + Tailwind, manual text inputs for folder paths (no picker), two separate startup commands, a fixed dark theme with light blue accents, and explicit exclusion of md_gen/md_mrg runtime integration in this phase.

## 2. Final Executive Summary
This onboard delivers a webapp shell under `src/webapp/` with a FastAPI backend and a React + Vite + Tailwind frontend. The implementation is limited to the single-window layout skeleton and a functional Settings view that loads and saves configuration through backend APIs to `data/config/settings.json`. Workflow execution, previews, and merge editing are intentionally deferred to later phases.

## 3. Consolidated Requirements & Acceptance Criteria
- **Requirement WO-01:** Webapp Scaffold Under `src/webapp/`
  - **Description:** Create `src/webapp/backend/` for FastAPI and `src/webapp/frontend/` for React + Vite + Tailwind, including minimal manifests and startup documentation for local development.
  - **Acceptance Criteria:**
    - [ ] Given a fresh clone, when running the documented backend startup command, then the FastAPI server starts locally and `GET /health` returns `{"status": "ok"}`.
    - [ ] Given a fresh clone, when running the documented frontend startup command, then the React app serves locally and loads in a browser without startup errors.

- **Requirement WO-02:** Single-Window Workflow Shell
  - **Description:** Implement a collapsible left side panel and five horizontal main panels in order: source list, source preview, `batch_mrg.json` panel, merge-document preview, output list. Workflow panels are placeholders only.
  - **Acceptance Criteria:**
    - [ ] Given the app is open, when the workflow screen loads, then all five labeled horizontal panels are visible in the specified order.
    - [ ] Given the app is open, when the user toggles the side panel, then the panel hides and shows without leaving the screen.
    - [ ] Given the side panel is visible, when the user switches between Workflow and Settings, then the side-panel content updates accordingly.

- **Requirement WO-03:** Fixed Visual Theme
  - **Description:** Apply a fixed dark theme with light blue accents across the frontend with no theme-switching support.
  - **Acceptance Criteria:**
    - [ ] Given the frontend is loaded, when the user views the interface, then the app consistently uses dark styling with light blue accents.
    - [ ] Given the frontend is loaded, when inspecting available controls, then no theme toggle or alternate theme selector exists.

- **Requirement WO-04:** Settings Load and Save Flow
  - **Description:** Implement a Settings view that edits and persists required values from `data/config/settings.json`: OCR model endpoint/model/timeout/retries, language model endpoint/model/timeout/retries, source folder path, and output folder path.
  - **Acceptance Criteria:**
    - [ ] Given the Settings view opens, when data is loaded from `GET /api/settings`, then all current settings values are shown in the corresponding fields.
    - [ ] Given the user edits settings and submits, when the payload is valid, then `PUT /api/settings` updates `data/config/settings.json` with the new values.
    - [ ] Given the user submits an invalid endpoint URL, when backend validation runs, then the API returns HTTP 422 and the UI displays inline validation feedback.
    - [ ] Given settings are saved successfully, when the save completes, then the UI shows a transient success confirmation.

- **Requirement WO-05:** Manual Folder Path Entry
  - **Description:** Configure source and output folders as plain text inputs in Settings; this phase excludes browse/picker interactions.
  - **Acceptance Criteria:**
    - [ ] Given the Settings view is open, when reviewing folder fields, then source and output folders are editable text inputs.
    - [ ] Given valid path strings are entered and saved, when the app restarts, then `source_folder` and `output_folder` persist in `data/config/settings.json`.
    - [ ] Given the user inspects folder controls, when looking for directory browsing actions, then no Browse button or folder picker is present.

- **Requirement WO-06:** Backend Configuration API Contract
  - **Description:** Expose JSON endpoints `GET /health`, `GET /api/settings`, and `PUT /api/settings`; validate settings with Pydantic; do not invoke `md_gen` or `md_mrg` in this onboard.
  - **Acceptance Criteria:**
    - [ ] Given a request to `GET /api/settings`, when the backend reads configuration, then it returns the full parsed JSON from `data/config/settings.json`.
    - [ ] Given a request to `PUT /api/settings` with a schema-valid payload, when processing completes, then the backend writes updates atomically to `data/config/settings.json`.
    - [ ] Given the backend is running, when opening `/docs`, then OpenAPI documentation for exposed endpoints is available.

## 4. Final Scope & Constraints
- **In-Scope:** Scaffold `src/webapp/backend/` and `src/webapp/frontend/`; implement FastAPI settings endpoints; implement the shell UI layout; implement Settings load/save flow; add and persist `source_folder` and `output_folder` keys in config JSON files; use a fixed dark theme with light blue accents.
- **Out-of-Scope:** Running `md_gen`/`md_mrg`; source/output listing population; source/merge previews; `batch_mrg.json` viewing or editing; folder picker UX; authentication/authorization; database integration; Electron packaging; long-running job execution infrastructure in this phase.
- **Technical Constraints & Edge Cases:** Configuration writes must be atomic to prevent corruption; folder path strings must be accepted even when directories do not yet exist; frontend must access settings only via backend API (no duplicated config reader logic); backend must allow local dev CORS between frontend and API ports; webapp structure must remain under `src/webapp/`; future long-task execution should follow a durable job-runner pattern with run IDs, append-only status events, and polling-first progress with optional SSE evolution, but that is not implemented in this onboard.

**LOCKED**