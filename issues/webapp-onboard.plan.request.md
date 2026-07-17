# Webapp Onboard Request

## Goal
Start the backend and frontend implementation for dir2md with a local-first architecture:

- Backend in Python using FastAPI.
- Frontend in TypeScript.
- No database.
- Configuration persisted only in `data/config/settings.json`.

This file is an initial request draft for later refinement and implementation planning.

## Product Context
The project already has two CLI modules:

- `md_gen`: source discovery, OCR, markdown generation, and `batch.json` creation.
- `md_mrg`: plan/apply merge workflow, `batch_mrg.json`, and merge outputs.

The web layer should orchestrate these existing modules instead of re-implementing their logic.

## UX Scope (Single Main Window)
The app should provide one main workflow screen with a horizontal layout (left to right):

1. List of current files in source folder.
2. Preview of the selected source file.
3. `batch_mrg.json` viewer/editor panel.
4. Preview of the selected document from the `batch_mrg.json` list/panel.
5. List of files in output folder.

Additional navigation:

- A left side panel that can be shown/hidden.
- The side panel switches between:
  - Workflow view.
  - Settings view.

## Technical Constraints
- Local-first operation (no cloud dependency required for app orchestration).
- No user accounts, auth, or multi-tenant features.
- No relational database.
- Use existing local configuration files under `data/config`.
- Preserve module boundaries:
  - `src/md_gen` and `src/md_mrg` contain core processing logic.
  - New backend should orchestrate them through explicit service boundaries.

## Architecture Direction Chosen
Primary direction selected:

- Backend: FastAPI (preferred over Django for this utility-style local app).
- Frontend: TypeScript web app.
- Desktop packaging: Electron is a possible later phase, not mandatory for phase 1.

## Alternatives Considered (Knowledge Record)
Framework alternatives discussed besides Django/FastAPI include:

- Flask
- Litestar
- Starlette
- Quart
- Sanic
- Falcon
- Pyramid
- aiohttp.web
- Tornado
- Bottle / CherryPy

Decision rationale at this stage:

- FastAPI selected for typed contracts, async readiness, and smooth integration with TypeScript frontend.
- Electron compatibility does not block FastAPI; backend can still run as a local process and be consumed by an Electron-hosted frontend later.

## Phase 1 In-Scope (Web First)
- Build a local FastAPI backend for file/config/workflow orchestration.
- Build a TypeScript frontend for the single-window workflow UI.
- Support run/plan/apply actions using existing `md_gen` and `md_mrg` logic.
- Read/write settings from `data/config/settings.json`.
- Show source and output file lists and previews.
- Show and edit/review `batch_mrg.json` before apply.

## Out-of-Scope for Phase 1
- User accounts, authentication, and authorization.
- Database integration.
- Multi-user collaboration.
- Cloud deployment requirements.
- Mandatory desktop packaging.

## Phase 2 Candidate Scope (Optional)
- Wrap frontend as desktop app using Electron.
- Manage backend lifecycle inside desktop packaging flow.
- Add desktop-specific file integration and packaging pipeline.

## Initial Acceptance Criteria
- A FastAPI server starts locally and exposes endpoints required by workflow UI.
- Settings can be loaded and saved through API to `data/config/settings.json`.
- UI displays source list, selected source preview, `batch_mrg.json` panel, selected merge-doc preview, and output list.
- UI includes show/hide left panel and switches between Workflow and Settings.
- User can trigger plan/apply flows from UI and see resulting file updates.
- No database is introduced.

## Open Questions For Refinement
- Should `batch_mrg.json` editing be free-form JSON or constrained through structured controls?
**User: this will be address in a future task. This task is only the onboard webapp with no immediate funtionally, We will only create the layout, edit/save of settings, and selection of source and output folder. Nothing more for this onboard.**

- What preview formats are required initially (markdown only, image only, PDF preview, or all)?
**User: For simplifity to avoid expendive PDF viewer, we can go with image and markdown (code and preview). md_gen internally generate small image on memory, we could adapt it to save them for preview purposes (with a contraint of number of pages, we don't want to extract pages for a 100-pages pdf). But this is out of the scope of this onboard.**

- What is the preferred backend execution model for long tasks (in-process background tasks, subprocess calls, or queue abstraction)?
**User: not sure, but it is possible for the task runs for several minunes, so it must be robuts enough. Propose a best practice design pattern for this. We will want to support some kind of progress bar or status (and logs maybe in the future).**

- What progress reporting is required (polling vs SSE/WebSocket)?
**User: I don't know, not familiar or expert in this area. Propose a wel stablish and best practice design pattern for proress report.**

- What minimum packaging strategy is expected for first internal distribution (web-only runbook vs packaged executable)?
**User: web only, I don't plan to distribute the package any time soon. Right now is for personal use.**

## Notes

**User: we will want to store the webapp in the folder `/src/webapp` and there create any subfolder for backend, frontend, and others.

---

# Refinement Iteration 1
**Status:** PENDING USER FEEDBACK

## 1. Executive Summary
This onboard task scaffolds the `dir2md` web application shell: a FastAPI backend and a TypeScript frontend co-located under `src/webapp/`. Deliverables are limited to the full layout skeleton, a functional Settings view that reads/writes `data/config/settings.json`, and folder-selection controls for source and output directories. No workflow processing (md_gen, md_mrg invocation, previews, or batch_mrg.json editing) is included.

## 2. Refined Requirements & Acceptance Criteria

- **Requirement WO-01:** Project scaffold under `src/webapp/`
  - **Description:** Create `src/webapp/backend/` (FastAPI app) and `src/webapp/frontend/` (TypeScript app) with minimal boilerplate, dependency manifests, and a README describing how to start each.
  - **Acceptance Criteria:**
    - [ ] Given a fresh clone, when running the documented startup command(s), the FastAPI server starts and responds to `GET /health` with `{"status": "ok"}`.
    - [ ] Given a fresh clone, when running the documented frontend start command, the UI is served and loads in a browser without errors.

- **Requirement WO-02:** Single-window layout shell
  - **Description:** Implement the full horizontal panel layout (source list | source preview | batch_mrg panel | merge-doc preview | output list) and a collapsible left side panel with Workflow / Settings tabs. All panels are empty placeholders except Settings; no data is loaded into them.
  - **Acceptance Criteria:**
    - [ ] Given the app is open, the five horizontal panels are visible with labelled placeholder content.
    - [ ] Given the app is open, the left side panel is visible and can be toggled hidden/shown via a button.
    - [ ] Given the left panel is open, clicking "Workflow" and "Settings" switches the panel view accordingly.

- **Requirement WO-03:** Settings view — load and save `settings.json`
  - **Description:** The Settings panel renders form fields for all top-level editable fields in `data/config/settings.json` (OCR model endpoint/model/timeout/retries, Language model endpoint/model/timeout/retries, source folder path, output folder path). On load the form is populated from a `GET /api/settings` response. On save the form posts to `PUT /api/settings`, which writes the updated values back to `data/config/settings.json`.
  - **Acceptance Criteria:**
    - [ ] Given the Settings view is opened, all current values from `data/config/settings.json` are pre-populated in the form.
    - [ ] Given the user changes a field and clicks Save, `data/config/settings.json` is updated with the new value.
    - [ ] Given an invalid endpoint URL is submitted, the API returns a 422 validation error and the UI shows an inline error message.
    - [ ] Given a save succeeds, the UI shows a transient success notification.

- **Requirement WO-04:** Source and output folder selection
  - **Description:** In the Settings view, the source folder and output folder fields include a "Browse" action that allows the user to pick a directory path. The selected path is stored in `data/config/settings.json` under new keys `source_folder` and `output_folder`.
  - **Acceptance Criteria:**
    - [ ] Given the user clicks "Browse" for source folder, a folder-selection interaction is available and the chosen path is populated in the field.
    - [ ] Given the user saves Settings, `source_folder` and `output_folder` values persist in `data/config/settings.json` across app restarts.

- **Requirement WO-05:** Backend API contract
  - **Description:** The FastAPI backend exposes at minimum: `GET /health`, `GET /api/settings`, `PUT /api/settings`. All endpoints return JSON. The backend does not invoke `md_gen` or `md_mrg` in this phase.
  - **Acceptance Criteria:**
    - [ ] `GET /api/settings` returns the full parsed content of `data/config/settings.json`.
    - [ ] `PUT /api/settings` accepts a JSON body, validates it against a Pydantic model, and writes back to `data/config/settings.json`.
    - [ ] All endpoints have OpenAPI docs auto-generated at `/docs`.

## 3. Scope & Constraints

- **In-Scope:**
  - `src/webapp/backend/`: FastAPI app, settings endpoints, Pydantic models for `settings.json`.
  - `src/webapp/frontend/`: TypeScript app, full layout shell with placeholder panels, Settings form with load/save.
  - Adding `source_folder` and `output_folder` keys to `data/config/settings.json` and `data/config/settings-default.json`.
  - `src/common/config.py` may need minor updates to expose the new folder keys; no other common module changes.

- **Out-of-Scope:**
  - Invoking `md_gen` or `md_mrg` from the UI or backend.
  - File listing in source/output panels (placeholder only).
  - Source file or merge-doc previews.
  - `batch_mrg.json` viewer/editor.
  - Long-running task execution model and progress reporting (deferred to a future task).
  - Authentication, authorization, or multi-user support.
  - Desktop/Electron packaging.

- **Technical Constraints / Edge Cases:**
  - `data/config/settings.json` must remain valid JSON at all times; the backend must write atomically (write to temp file, then rename) to prevent corruption on crash.
  - Folder paths entered by the user may not yet exist; the API should accept them without existence validation (the user may be configuring before creating the folder).
  - The frontend dev server and FastAPI server run on different ports; CORS must be configured on the backend for local dev.
  - `src/webapp/frontend/` must NOT duplicate any settings-reading logic from `src/common/config.py`; the frontend reads settings exclusively through the API.

## 4. Open Design Choices (Questions for User)

- **[Technical]:** What TypeScript UI framework should be used for the frontend?
  - Options: **React** (most common, large ecosystem), **Vue 3** (lighter, options/composition API), **Svelte** (minimal boilerplate, compile-time), **Vanilla TypeScript** (no framework dependency).
  - Recommendation: React with Vite as the build tool, as it aligns with the TypeScript contract goal and has the widest hiring/tooling support.
  **User: ok, lets use react with Vite, I am not a web developert.**

- **[Technical]:** What CSS/styling approach is preferred?
  - Options: **Tailwind CSS** (utility-first, no component library needed), **Plain CSS / CSS Modules** (zero dependency), **a light component library** (e.g. shadcn/ui for React, or similar).
  - Recommendation: Tailwind CSS for rapid layout work without a heavy component library. **User: ok, lets go with Tailwind.**

- **[UX/UI]:** For folder selection ("Browse" button in Settings), what is the preferred interaction model?
  - **Option A — Text input only:** User types the path manually. Simple, works in all browsers, no extra backend needed.
  - **Option B — Backend filesystem browser API:** Backend exposes a directory-listing endpoint; frontend shows a simple tree/modal to navigate and pick a folder. More work but avoids manual path entry.
  - **Option C — HTML folder input (`webkitdirectory`):** Browser native picker, but only returns file objects (not a clean path string) and has inconsistent cross-browser behavior.
  - Recommendation: **Option A** for this onboard (text input with a placeholder hint like `C:/Users/.../docs`), with Option B as a future enhancement.
  **User: text input.**

- **[Technical]:** Should there be a single unified startup command (e.g. `uv run start` that launches both backend and frontend dev server), or are two separate commands acceptable for this onboard phase?
  - Recommendation: Two separate commands documented in a README is sufficient for personal use at this stage.
  **User: ok, two commands.**

  ## Notes:

  **User: We will want a fixed dark theme with light blue accents. We don't need to support change the theme.**

---

# Refinement Iteration 2
**Status:** LOCKED

## 1. Executive Summary
This onboard task is now narrowed to a webapp shell under `src/webapp/` with a FastAPI backend and a React + Vite + Tailwind frontend. Phase 1 only includes the application scaffold, the fixed dark-theme layout shell, and a Settings view that loads and saves configuration values, including manual source and output folder path entry, through the backend API.

## 2. Refined Requirements & Acceptance Criteria

- **Requirement WO-01:** Webapp scaffold under `src/webapp/`
  - **Description:** Create `src/webapp/backend/` for the FastAPI app and `src/webapp/frontend/` for the React + Vite + Tailwind app, with minimal manifests and startup documentation for local development.
  - **Acceptance Criteria:**
    - [ ] Given a fresh clone, when running the documented backend startup command, the FastAPI server starts locally and `GET /health` returns `{"status": "ok"}`.
    - [ ] Given a fresh clone, when running the documented frontend startup command, the React app is served locally and loads in a browser without startup errors.

- **Requirement WO-02:** Single-window workflow shell
  - **Description:** Implement the full single-window layout with a collapsible left panel and five horizontal main panels in this order: source list, source preview, `batch_mrg.json` panel, merge-document preview, output list. All workflow panels are placeholders only in this onboard phase.
  - **Acceptance Criteria:**
    - [ ] Given the app is open, when the main workflow screen loads, then the five labelled horizontal panels are visible in the specified order.
    - [ ] Given the app is open, when the user toggles the left side panel, then the panel hides and shows without navigating away from the screen.
    - [ ] Given the left side panel is visible, when the user switches between Workflow and Settings, then the panel content updates to the selected section.

- **Requirement WO-03:** Fixed visual theme
  - **Description:** Apply a fixed dark theme with light blue accents across the onboard frontend. Theme switching is not supported.
  - **Acceptance Criteria:**
    - [ ] Given the frontend is loaded, when the user views the app, then the UI uses a dark theme with light blue accent styling.
    - [ ] Given the frontend is loaded, when the user inspects the layout, then no theme toggle or alternate theme control is present.

- **Requirement WO-04:** Settings load and save flow
  - **Description:** The Settings view renders editable form fields for all required configuration values sourced from `data/config/settings.json`, including OCR model endpoint, OCR model name, OCR timeout, OCR retries, language model endpoint, language model name, language model timeout, language model retries, source folder path, and output folder path. The frontend loads values through `GET /api/settings` and saves changes through `PUT /api/settings`.
  - **Acceptance Criteria:**
    - [ ] Given the Settings view is opened, when the form loads, then all current values from `data/config/settings.json` are displayed in the corresponding fields.
    - [ ] Given the user edits one or more settings and submits the form, when the API accepts the payload, then `data/config/settings.json` is updated with the new values.
    - [ ] Given the user submits an invalid endpoint URL, when the backend validates the request, then the API returns a 422 response and the UI shows the validation error inline.
    - [ ] Given the user saves valid settings successfully, when the save completes, then the UI shows a transient success confirmation.

- **Requirement WO-05:** Manual folder path entry
  - **Description:** Source and output folders are configured as plain text path fields in the Settings view. This onboard phase does not include a native folder picker, browser-based folder picker, or backend filesystem browser.
  - **Acceptance Criteria:**
    - [ ] Given the Settings view is opened, when the user reviews the folder configuration area, then source and output folder values are editable as text inputs.
    - [ ] Given the user enters valid path strings and saves settings, when the app is restarted, then the saved `source_folder` and `output_folder` values persist in `data/config/settings.json`.
    - [ ] Given the user views the Settings form, when they look for directory browsing controls, then no Browse button or folder picker control is present in this phase.

- **Requirement WO-06:** Backend API contract for configuration
  - **Description:** The FastAPI backend exposes `GET /health`, `GET /api/settings`, and `PUT /api/settings`, all returning JSON. The backend validates settings through Pydantic models and does not invoke `md_gen` or `md_mrg` during this onboard phase.
  - **Acceptance Criteria:**
    - [ ] Given a request to `GET /api/settings`, when the backend reads the config file, then it returns the full parsed JSON content of `data/config/settings.json`.
    - [ ] Given a request to `PUT /api/settings`, when the payload matches the settings schema, then the backend writes the updated JSON back to `data/config/settings.json` atomically.
    - [ ] Given the backend is running, when the user opens `/docs`, then OpenAPI documentation for the available endpoints is present.

## 3. Scope & Constraints
- **In-Scope:** Scaffold `src/webapp/backend/` and `src/webapp/frontend/`; implement FastAPI settings endpoints; build the React + Vite + Tailwind layout shell; implement the Settings form; add `source_folder` and `output_folder` to `data/config/settings.json` and `data/config/settings-default.json`; apply a fixed dark theme with light blue accents.
- **Out-of-Scope:** Any invocation of `md_gen` or `md_mrg`; actual source/output file listing; source previews; merge-document previews; `batch_mrg.json` viewing or editing; folder picker UX beyond plain text path entry; authentication; databases; Electron packaging; runtime orchestration for long-running jobs in this phase.
- **Technical Constraints / Edge Cases:** `data/config/settings.json` must be written atomically to avoid corruption; folder path strings must be accepted even if the target directories do not yet exist; the frontend must read and write settings only through the backend API; CORS must be configured for local frontend/backend development on separate ports; the webapp must live under `src/webapp/` with backend and frontend subfolders; future workflow execution should follow a job-runner pattern with durable run IDs, append-only status events, and progress delivery via polling-first APIs with an SSE upgrade path, but no such execution infrastructure is implemented in this onboard.

**LOCKED**