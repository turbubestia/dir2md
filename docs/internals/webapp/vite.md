# Vite

## What It Is

Vite is a frontend build tool and development server. It serves the app during
development, bundles it for production, and gives fast reloads while you edit
files.

## What Problem It Solves

Without a tool like Vite, you would have to manage a lot of manual browser
setup, bundling, and refresh logic. Vite handles the development server,
module loading, and production build pipeline for you.

## Quick Start

1. Install dependencies with npm.
2. Run the dev server with `npm run dev`.
3. Open the local URL Vite prints.
4. Edit source files and watch the page refresh.

The production build command is usually `npm run build`.

## How This Project Uses It

The frontend app lives in `src/webapp/frontend/` and is managed by Vite:

- `src/webapp/frontend/package.json` defines `dev`, `build`, and `preview`.
- `src/webapp/frontend/vite.config.ts` configures the dev server and proxies
	`/health` and `/api` to the FastAPI backend on port `8000`.
- `src/webapp/frontend/index.html` is the HTML shell Vite loads.
- `src/webapp/frontend/src/main.tsx` is the browser entry point Vite mounts.

In this project, Vite keeps the browser UI running locally while the Python
backend runs separately.

## When You Would Edit It

Edit Vite configuration when you need to change the frontend dev port, backend
proxy settings, or build behavior.
