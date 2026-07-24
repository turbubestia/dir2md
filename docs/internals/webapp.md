# dir2md Webapp Architecture

This document describes the current webapp structure in the repository: a
FastAPI backend, a Vite + React + Tailwind frontend, and a small set of shared
Pydantic/TypeScript models that keep both halves aligned.

The main idea is simple:

- The backend owns persistence, workflow state, file preview routes, and the
	orchestration code that talks to `md_gen`, `md_mrg`, and the LLM test path.
- The frontend owns the screen layout, styling, local interaction state, and
	API calls.
- Shared JSON shapes are defined in `src/webapp/backend/models.py` and mirrored
	in `src/webapp/frontend/src/types.ts`.

## Folder Map

```text
src/webapp/
├── backend/
│   ├── app.py
│   ├── models.py
│   ├── settings_store.py
│   └── workflow.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── vite.config.ts
│   ├── postcss.config.js
│   └── src/
│       ├── App.tsx
│       ├── api.ts
│       ├── main.tsx
│       ├── styles.css
│       ├── types.ts
│       └── components/
│           ├── WorkspaceShell.tsx
│           ├── WorkflowPanel.tsx
│           ├── SettingsForm.tsx
│           ├── LlmTestPanel.tsx
│           ├── MarkdownViewer.tsx
│           └── MarkdownModeToggle.tsx
└── serve.py
```

## Backend

The backend is a single FastAPI application exported from
`src/webapp/backend/app.py`. The module builds the app with `create_app()` and
exports `app = create_app()` at import time, which is what `uvicorn` runs.

### Backend technology

- FastAPI for HTTP routes and Server-Sent Events.
- Pydantic for request and response validation.
- File-backed JSON persistence for settings.
- Internal orchestration against `md_gen`, `md_mrg`, and `llm_cli`.

### Backend responsibilities

- `src/webapp/backend/app.py` registers routes, CORS, and the `app` object.
- `src/webapp/backend/settings_store.py` reads and writes `data/config/settings.json` atomically and bootstraps it from `data/config/settings-default.json` when missing.
- `src/webapp/backend/models.py` defines the contract for settings, workflow discovery, workflow state, merge plans, LLM test payloads, and preview responses.
- `src/webapp/backend/workflow.py` owns the actual workflow state machine and file-oriented behavior.

### Backend API surface

The current browser UI talks to these routes:

- `GET /health` for liveness.
- `GET /api/settings` and `PUT /api/settings` for the shared settings file.
- `POST /api/workflow/start` for source/output discovery.
- `POST /api/workflow/ocr` for OCR generation.
- `GET /api/workflow/state` for the current workflow state snapshot.
- `GET /api/workflow/merge-plan` and `PUT /api/workflow/merge-plan` for the editable merge plan.
- `POST /api/workflow/merge` for merge execution.
- `GET /api/workflow/merge-results` for merge result metadata.
- `GET /api/workflow/events` for live state updates over SSE.
- `GET /api/workflow/source-preview/{file_id}` for source file previews.
- `GET /api/workflow/ocr-preview/{artifact_id}` for OCR artifact previews.
- `GET /api/workflow/markdown-preview/{artifact_id}` for markdown previews.
- `GET /api/workflow/merge-result-preview/{result_id}` and `GET /api/workflow/merge-result-markdown/{result_id}` for merge result inspection.
- `GET /api/llm-test-prompt/{name}` and `PUT /api/llm-test-prompt/{name}` for the local prompt files used by the LLM test panel.
- `POST /api/workflow/llm-test` for the local LLM test run.

### Backend boundaries

- `settings_store.py` is the only place that should directly touch the shared
	settings JSON on disk.
- `workflow.py` contains the business rules for discovery, preview validation,
	OCR, merge, and test execution.
- `app.py` should stay thin: route registration, error translation, and CORS.

If you need to change backend behavior, start by looking in `workflow.py`.
If you need to change how settings are stored, start in `settings_store.py`.
If you need to add or adjust an HTTP endpoint, start in `app.py`.

## Frontend

The frontend is a single-page React app built with Vite and styled with
Tailwind CSS. The browser entry point is `src/webapp/frontend/index.html`, which
loads `src/webapp/frontend/src/main.tsx`, which mounts `App.tsx`.

### Frontend technology

- React 18 for the UI.
- Vite for dev server and production builds.
- Tailwind CSS for the design system and reusable utility classes.
- `react-pdf` for PDF previews.
- `react-markdown`, `remark-gfm`, `remark-math`, `rehype-raw`,
	`rehype-sanitize`, `rehype-mathjax`, and `better-react-mathjax` for markdown
	and math rendering.

### Frontend module separation

- `src/webapp/frontend/src/App.tsx` is the top-level app component.
- `src/webapp/frontend/src/components/WorkspaceShell.tsx` owns the main shell,
	sidebar, and workflow/settings section switching.
- `src/webapp/frontend/src/components/WorkflowPanel.tsx` owns the workflow UI,
	source discovery, OCR stage UI, merge results, preview panes, and the rename
	placeholder stage.
- `src/webapp/frontend/src/components/SettingsForm.tsx` owns the settings editor
	form and validation display.
- `src/webapp/frontend/src/components/LlmTestPanel.tsx` owns the local prompt
	editor and LLM test UI.
- `src/webapp/frontend/src/components/MarkdownViewer.tsx` renders markdown in
	code or preview mode.
- `src/webapp/frontend/src/api.ts` is the fetch layer for all backend calls.
- `src/webapp/frontend/src/types.ts` mirrors the backend schemas in TypeScript.

### Frontend layout flow

The visual shell flows like this:

`index.html` -> `main.tsx` -> `App.tsx` -> `WorkspaceShell.tsx` ->
`WorkflowPanel.tsx` / `SettingsForm.tsx` / `LlmTestPanel.tsx`

`WorkspaceShell.tsx` controls the left navigation and the high-level section
choice. `WorkflowPanel.tsx` controls the multi-stage workflow canvas and its
three-pane workspace. `SettingsForm.tsx` and `LlmTestPanel.tsx` are the two
secondary surfaces in the Settings section.

## How The Two Halves Connect

The frontend talks to the backend through `src/webapp/frontend/src/api.ts`.
That module uses `fetch()` for normal requests and `EventSource` for the SSE
workflow stream.

In local development, `vite.config.ts` proxies `/health` and `/api` to
`http://127.0.0.1:8000`, so the browser can talk to the FastAPI server without
manual CORS or cross-origin configuration. The backend still installs CORS in
`app.py` for direct access and testability.

Shared state is exchanged as JSON:

- Settings are loaded from and saved to `data/config/settings.json`.
- Workflow state is returned as `WorkflowState` / `WorkflowDiscoveryResponse`
	objects.
- Preview routes return files or markdown payloads directly.

## What To Change For Common UI Edits

### Colors and theme

Start with `src/webapp/frontend/tailwind.config.ts`. That file defines the core
`shell` and `accent` colors used across the app.

Then update `src/webapp/frontend/src/styles.css`, which contains the component
classes that actually apply those tokens to panels, buttons, rows, preview
frames, workflow stages, and markdown rendering.

If you want to change the default page shell colors, also check
`src/webapp/frontend/index.html`, which sets the `dark` class on the `<html>`
element and the base background/text classes on `<body>`.

### Layout and page structure

For the overall screen layout, edit
`src/webapp/frontend/src/components/WorkspaceShell.tsx`.

For the workflow page layout, edit
`src/webapp/frontend/src/components/WorkflowPanel.tsx`.

For the settings page layout, edit
`src/webapp/frontend/src/components/SettingsForm.tsx`.

For markdown preview behavior or PDF rendering behavior, edit
`src/webapp/frontend/src/components/MarkdownViewer.tsx` and the preview blocks
inside `WorkflowPanel.tsx`.

### Spacing, panels, and reusable component styles

Most of the reusable styling lives in `src/webapp/frontend/src/styles.css`.
That file defines the panel chrome, buttons, workflow stage buttons, list row
variants, tree row variants, preview frames, markdown styling, and the PDF
viewer chrome.

If a change affects many controls at once, prefer changing the shared CSS class
in `styles.css` instead of editing every component individually.

### Behavior and data flow

If the UI action should call the backend, change `src/webapp/frontend/src/api.ts`
and the corresponding backend route in `src/webapp/backend/app.py` and
`src/webapp/backend/workflow.py`.

If the UI action should only affect local state, keep it in the relevant React
component and avoid adding a backend route.

## Where The Important Code Lives

- Backend app bootstrap and routes: `src/webapp/backend/app.py`
- Workflow orchestration and previews: `src/webapp/backend/workflow.py`
- Settings persistence: `src/webapp/backend/settings_store.py`
- Shared backend schemas: `src/webapp/backend/models.py`
- Frontend entry point: `src/webapp/frontend/src/main.tsx`
- Frontend shell and page composition: `src/webapp/frontend/src/App.tsx` and
	`src/webapp/frontend/src/components/WorkspaceShell.tsx`
- Workflow UI and previews: `src/webapp/frontend/src/components/WorkflowPanel.tsx`
- Settings form: `src/webapp/frontend/src/components/SettingsForm.tsx`
- Prompt editor and test panel: `src/webapp/frontend/src/components/LlmTestPanel.tsx`
- Shared fetch layer: `src/webapp/frontend/src/api.ts`
- Shared TypeScript contracts: `src/webapp/frontend/src/types.ts`
- Theme tokens and reusable styles: `src/webapp/frontend/tailwind.config.ts`
	and `src/webapp/frontend/src/styles.css`

## Local Dev Entry Points

There are two common ways to run the app locally:

- `src/webapp/serve.py --backend` starts the FastAPI server.
- `src/webapp/serve.py --frontend` starts the Vite dev server.

The frontend dev server expects the backend on port `8000`, and the browser UI
is served on port `5173`.

## Practical Editing Rule Of Thumb

- Change layout in React components.
- Change colors and reusable visual rules in Tailwind config plus `styles.css`.
- Change API behavior in the backend `app.py` / `workflow.py` pair.
- Change persisted configuration rules in `settings_store.py` and
	`models.py`.

If you are unsure where a behavior belongs, start with the component that owns
the visible screen, then follow its API call into `src/webapp/frontend/src/api.ts`
and from there into the matching backend route.
