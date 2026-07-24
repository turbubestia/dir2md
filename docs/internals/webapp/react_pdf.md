# react-pdf

## What It Is

`react-pdf` is a React library for displaying PDF files in the browser. It wraps
PDF.js and exposes React components for loading and rendering pages.

## What Problem It Solves

Browsers can open PDFs directly, but that does not always fit into an app layout
or preview workflow. `react-pdf` lets you place a PDF viewer inside your own UI,
control zoom and scrolling, and style the container around it.

## Quick Start

1. Import `Document` and `Page` from `react-pdf`.
2. Set the PDF worker source.
3. Load a file URL or byte source.
4. Render one or more pages inside your React layout.

Example:

```tsx
import { Document, Page } from 'react-pdf'

<Document file="/example.pdf">
  <Page pageNumber={1} />
</Document>
```

## How This Project Uses It

This project uses `react-pdf` in `src/webapp/frontend/src/components/WorkflowPanel.tsx`.
That panel uses the library to show PDF previews for workflow items and merge
results. The code also configures the PDF worker with `pdfjs.GlobalWorkerOptions.workerSrc`.

The supporting styling lives in `src/webapp/frontend/src/styles.css`, where the
PDF frame, toolbar, viewer area, and page sizing are defined.

## Why It Matters Here

The app needs to inspect PDF sources without forcing the user to leave the
workflow screen. `react-pdf` lets the project show those files inline, next to
the rest of the workflow state.

## When You Would Edit It

Edit the PDF viewer code when you want to change zoom behavior, page layout,
worker setup, or the surrounding preview chrome.
