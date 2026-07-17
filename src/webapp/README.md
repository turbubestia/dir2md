# dir2md Webapp

This directory contains the local-first webapp scaffold for dir2md. It is
intentionally limited to a single-window UI shell and a Settings editor in this
phase. Workflow execution, previews, merge editing, and `batch_mrg.json`
interactions are deferred to later phases.

## Layout

```
src/webapp/
├── backend/          FastAPI settings API
│   ├── app.py        FastAPI application factory and routes
│   ├── models.py     Pydantic settings schema
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
    │       └── SettingsForm.tsx
    └── package.json
```

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
- ✅ Pydantic validation and atomic writes to `data/config/settings.json`
- ✅ Fixed dark theme with light blue accents
- ✅ Collapsible left side panel with Workflow / Settings sections
- ✅ Five horizontal workflow placeholder panels
- ✅ Settings form with OCR, language model, source/output folders, verbose, and overwrite
- ❌ Running `md_gen` or `md_mrg` from the browser
- ❌ Source/output listing population
- ❌ Source/merge previews
- ❌ `batch_mrg.json` viewing or editing
- ❌ Folder picker UX
- ❌ Authentication / authorization
- ❌ Database integration
