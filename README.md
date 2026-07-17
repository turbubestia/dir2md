# dir2md

Local-first tooling for turning PDFs and images into markdown, then merging related loose scans into unified documents.

## Current Status

The project now has two working command-line modules:

- `md-gen` prepares OCR inputs and writes per-source metadata and markdown artifacts in a deterministic local pipeline.
- `md-mrg` consumes the metadata JSON produced by `md-gen`, plans how loose pages should be grouped, and applies the plan to generate merged markdown and PDF outputs.

The workflow is intentionally split so the OCR stage and the merge stage stay independently testable. `md-gen` focuses on document ingestion and page-level output generation. `md-mrg` focuses on document reconstruction, reviewable merge planning, and final output assembly.

## What Each Module Does

### `md-gen`

`md-gen` is the OCR and artifact-preparation entrypoint. It:

- scans one source directory level (non-recursive) and consumes only `.pdf`, `.png`, `.jpg`, `.jpge`
- rasterizes PDF pages into `output/temp/images`
- resizes images to the configured model limit
- estimates token budget per page before OCR
- calls the local llama.cpp-compatible OCR and summary endpoints
- writes OCR markdown into `output/temp/markdown`
- writes metadata JSON into `output/temp/metadata`
- records provenance so later stages can trace where each fragment came from

### `md-mrg`

`md-mrg` is the merge and apply entrypoint. It:

- loads `source/batch.json` produced by `md-gen`
- groups loose image pages using adjacent-pair LLM scoring
- writes a reviewable merge plan into `source/batch_mrg.json`
- applies the reviewed plan to write deterministic merged artifacts
- writes execution statuses into `source/batch_mrg_result.json`

## Setup

### Linux Setup (Ubuntu/Debian)

Install Python and image build dependencies:

```bash
sudo apt update
sudo apt install -y \
	python3 \
	python3-venv \
	python3-pip \
	python3-dev \
	libjpeg-dev
```

Install project dependencies with `uv`:

```bash
uv sync
```

## Using `md-gen`

Run the OCR foundation pipeline:

```bash
uv run md-gen \
	--source ./samples/invoice-set \
	--output ./samples/out \
	--overwrite
```

Common options:

- `--source` is required and must be an existing directory
- `--output` is required and is auto-created if missing
- `--summary-prompt` optionally points to a custom summary system-prompt file
- `--ocr-model-endpoint-url` sets the local OCR endpoint
- `--ocr-model-name` sets the OCR model identifier
- `--language-model-endpoint-url` sets the local summary endpoint
- `--language-model-name` sets the summary model identifier
- `--max-longest-edge-px` sets the image resize limit
- `--token-threshold` sets the token budget threshold
- `--dry-run` skips OCR and markdown persistence
- `--overwrite` replaces existing markdown outputs

Example with explicit paths:

```bash
uv run md-gen \
	--source /data/scans/incoming \
	--output /data/work/output \
	--summary-prompt /data/work/prompts/summary.txt
```

## Using `md-mrg`

Build the merge plan from `batch.json`:

```bash
uv run md-mrg \
	--source /data/work/output \
	--plan
```

Apply the reviewed merge plan:

```bash
uv run md-mrg \
	--source /data/work/output \
	--apply
```

Common `md-mrg` options:

- exactly one of `--plan` or `--apply` is required
- `--source` is required and must point to the `md-gen` output directory
- planner reads `source/batch.json` and writes `source/batch_mrg.json`
- planner compares only adjacent image records and keeps pdf records unchanged
- apply reads `source/batch_mrg.json`
- apply writes `source/merged-NNN.pdf` and `source/merger-NNN.md` for each successful image group
- apply writes run status metadata to `source/batch_mrg_result.json`
- apply deletes only loose markdown files from successfully merged groups
- apply never deletes original source image files

## Repository Layout

- `src/md_gen`: OCR ingestion, source discovery, rasterization, resizing, token budgeting, and markdown persistence
- `src/md_mrg`: merge planning and merge execution for loose page reconstruction
- `src/common`: shared llama.cpp-compatible gateway code
- `design/`: architecture notes, implementation plans, and issue docs
- `test/`: unit and integration tests

## Notes

- The project uses `uv` for dependency management and execution.
- Local llama.cpp-compatible services are expected to be running separately.
- The merge workflow is LLM-only in this phase and uses source-derived paths for plan/apply.

## Validation

Run the test suite with:

```bash
uv run pytest -q
```
