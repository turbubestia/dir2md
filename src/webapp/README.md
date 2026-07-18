# dir2md Webapp

This directory contains the local-first webapp scaffold for dir2md. It is
intentionally limited to a single-window UI shell, Settings editor, Start
discovery workflow, and local-only placeholder stages in this phase. OCR, merge,
rename, and `batch_mrg.json` persistence are deferred to later phases.

## Layout

```
src/webapp/
├── backend/          FastAPI settings and workflow discovery API
│   ├── app.py        FastAPI application factory and routes
│   ├── models.py     Pydantic settings and workflow schemas
│   ├── workflow.py   Start discovery and source preview validation
│   └── settings_store.py   Atomic read/write for data/config/settings.json
└── frontend/         React + Vite + Tailwind browser UI
    ├── src/
    │   ├── App.tsx
    │   ├── main.tsx
    │   ├── styles.css
    │   ├── api.ts
    │   ├── types.ts
    │   └── components/
    │       ├── WorkspaceShell.tsx
        │       ├── WorkflowPanel.tsx
    │       └── SettingsForm.tsx
    └── package.json
```

## API routes

- `GET /health` returns backend liveness.
- `GET /api/settings` loads the shared settings document.
- `PUT /api/settings` validates and saves the shared settings document.
- `POST /api/workflow/start` reads the configured source and output folders,
    discovers supported top-level PDF/image source files through `md_gen`
    discovery rules, and returns workflow metrics plus folder status messages.
- `GET /api/workflow/source-preview/{file_id}` streams a validated image source
    file from the current configured source folder. Preview ids are checked
    against the current discovery result before bytes are returned.

PDF preview is metadata-only in this phase. The OCR, Merge, and Rename stages in
the frontend are visual simulations only; they do not call backend workflow
endpoints and do not write output artifacts.

## Local development

You need two terminal sessions: one for the backend and one for the frontend.
Both run on your local machine only.

### Backend

From the repository root, run the FastAPI server through `uv`:

```powershell
uv run uvicorn webapp.backend.app:app --reload --port 8000
```

Verify the backend is up:

```powershell
curl http://127.0.0.1:8000/health
# Expected: {"status":"ok"}
```

OpenAPI documentation is available at `http://127.0.0.1:8000/docs` while the
server is running.

### Frontend

From `src/webapp/frontend`, run the Vite dev server:

```powershell
cd src/webapp/frontend
npm run dev
```

The dev server proxies `/health` and `/api` requests to the backend on
`http://127.0.0.1:8000`, so the frontend can talk to the local API without
additional CORS setup in most browsers.

Open `http://localhost:5173` in your browser.

## Build for static serving

To produce a production build of the frontend:

```powershell
cd src/webapp/frontend
npm run build
```

The static assets are written to `src/webapp/frontend/dist`.

## Scope of this phase

- ✅ FastAPI backend with `/health`, `GET /api/settings`, and `PUT /api/settings`
- ✅ `POST /api/workflow/start` for configured-folder discovery
- ✅ `GET /api/workflow/source-preview/{file_id}` for validated image previews
- ✅ Pydantic validation and atomic writes to `data/config/settings.json`
- ✅ Fixed dark theme with light blue accents
- ✅ Collapsible left side panel with Workflow / Settings sections
- ✅ Four-stage Workflow panel with Start discovery and simulated OCR/Merge/Rename
- ✅ Settings form with OCR, language model, source/output folders, verbose, and overwrite
- ❌ Running `md_gen` or `md_mrg` from the browser
- ❌ Running OCR, merge, or rename from the browser
- ❌ PDF rendering beyond metadata
- ❌ Merge previews backed by generated artifacts
- ❌ `batch_mrg.json` viewing or editing
- ❌ Folder picker UX
- ❌ Authentication / authorization
- ❌ Database integration
