# FastAPI

## What It Is

FastAPI is a Python web framework for building HTTP APIs. It uses normal Python
functions for routes and Pydantic models for validation and documentation.

## What Problem It Solves

It gives you a clean way to expose backend behavior to the browser without
writing low-level request parsing code. FastAPI also validates incoming JSON and
generates API docs automatically.

## Core Pieces To Understand

- **Framework (`fastapi`)**: defines routes, validation rules, and docs metadata.
- **Application object (`app`)**: the in-memory ASGI app that contains all routes
	and middleware.
- **ASGI server (`uvicorn`)**: the process that listens on a TCP port and forwards
	HTTP requests to the app object.

Think of it as:

1. FastAPI describes *what* your API is.
2. `app` is the runtime object that contains that API.
3. `uvicorn` is the executable server that runs the app.

## What ASGI Means

ASGI stands for **Asynchronous Server Gateway Interface**.

It is a standard contract between a Python web server and a Python web
application. The server (for example, `uvicorn`) receives HTTP traffic from the
network and passes each request to the ASGI app object, then returns the app's
response to the client.

Why this matters in practice:

1. It supports async request handling.
2. It supports long-lived connections like WebSockets and streaming.
3. It lets the same FastAPI app run on different ASGI-compatible servers.

## Quick Start

1. Create an app object with `FastAPI()`.
2. Add route functions with decorators like `@app.get()` and `@app.post()`.
3. Use Pydantic models for request and response bodies.
4. Run the app with `uvicorn` during development.

Example:

```py
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}
```

## Who Uses The `app` Object

In this repo, `src/webapp/backend/app.py` builds the application with
`create_app()` and exports `app = create_app()`.

The exported `app` is consumed by:

- `uvicorn` (directly or via `python -m uvicorn`) when you run
  `webapp.backend.app:app`.
- FastAPI internals, which use it to resolve route handlers, run middleware, and
  generate OpenAPI docs.
- Test code that can import app creation logic and exercise endpoints.

Important detail: application code should usually not "call" `app` directly.
Instead, code registers routes and middleware on it, and the ASGI server invokes
it per request.

## `uvicorn` In Development

`uvicorn` is a lightweight ASGI server commonly used for local development
because it starts fast and supports `--reload`.

In this project, development startup is done with commands like:

- `uv run uvicorn webapp.backend.app:app --reload --port 8000`
- `uv run serve --backend` (which internally starts `uvicorn` with reload)

`--reload` watches files and restarts automatically. That is convenient for local
work but not ideal for production stability/performance.

## What Is Used In Production

`uvicorn` itself is an ASGI server and can be used in production, but normally
without `--reload` and often with multiple workers under a process manager.

Common production patterns:

1. **`gunicorn` + `uvicorn` workers (Linux)**
	- Example: `gunicorn -k uvicorn.workers.UvicornWorker webapp.backend.app:app`
	- `gunicorn` manages worker processes, restarts, and lifecycle.
2. **Standalone `uvicorn` with workers**
	- Example: `uvicorn webapp.backend.app:app --host 0.0.0.0 --port 8000 --workers 2`
3. **ASGI server behind a reverse proxy**
	- Nginx/Caddy/Traefik terminates TLS and forwards to the ASGI server.

For this repository today, the documented workflow is **local-first development**.
A production deployment profile is not yet standardized in this codebase, so pick
one of the patterns above when deployment requirements are defined.

## How This Project Uses It

The webapp backend lives in `src/webapp/backend/`:

- `src/webapp/backend/app.py` creates the FastAPI app and registers routes.
- `src/webapp/backend/workflow.py` contains the workflow logic behind those
	routes.
- `src/webapp/backend/settings_store.py` loads and saves the shared settings
	file.

Startup entry points used by developers:

- `src/webapp/serve.py` starts backend dev mode through `python -m uvicorn`.
- `serve.bat` launches backend + frontend for local iteration.

FastAPI powers the settings API, workflow endpoints, preview routes, SSE event
stream, and LLM test prompt endpoints.

## When You Would Edit It

Edit FastAPI code when you want to add, remove, or change an HTTP endpoint or
adjust request/response handling.
