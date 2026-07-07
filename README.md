# dir2md

Convert PDF or image files to markdown using a local-first OCR pipeline.

## Phase 1 Status (Goal 2.2.1)

Phase 1 provides a dependency-ready foundation for `md-gen`:
- runtime and test dependencies managed with `uv`
- typed runtime configuration model
- CLI entrypoint scaffold (`md-gen`)
- artifact directory bootstrap for `im-temp`, `md-temp`, and log parent path

No OCR business logic is implemented in this phase.

## Linux Setup (Ubuntu/Debian)

Install Python and image build dependencies:

```bash
sudo apt update
sudo apt install -y \
	python3 \
	python3-venv \
	python3-pip \
	python3-dev \
	build-essential \
	pkg-config \
	libjpeg-dev \
	zlib1g-dev \
	libtiff-dev \
	libopenjp2-7-dev
```

Install project dependencies with `uv`:

```bash
uv sync
```

## CLI Foundation

Run the Phase 1 bootstrap command:

```bash
uv run md-gen --source ./samples --dry-run
```

Useful options:
- `--source` (repeatable): source file or directory inputs
- `--source-list-file` (repeatable): text file with one source path per line (`#` comment lines supported)
- `--output-dir`: future normalized output location
- `--im-temp-dir`: temporary rasterized/preprocessed image path
- `--md-temp-dir`: temporary markdown output path
- `--log-file`: plain text log destination
- `--model-endpoint-url`: local llama.cpp-compatible endpoint
- `--model-name`: OCR model identifier
- `--max-longest-edge-px`: image longest-edge limit (default `1540`)
- `--token-threshold`: OCR token budget threshold (default `16000`)
- `--dry-run` / `--no-dry-run`
- `--overwrite`

## Phase 2 Discovery Rules

- Supported source file types: PDF (`.pdf`) and images (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.webp`)
- Input modes: single file, directory scan (recursive), repeated `--source`, and repeated `--source-list-file`
- Discovery deduplicates repeated paths from all sources
- Work-item ordering is deterministic by normalized path ordering

## Phase 3 PDF Rasterization Rules

- PDF rendering uses `pypdfium2`
- Rasterized pages are written as PNG files in `im-temp`
- Output naming is deterministic: sanitized source stem + source hash + page number (e.g. `file-a1b2c3d4e5-p0001.png`)
- Page metadata tracks source path, source order index, page index/number, total pages, and output dimensions
- Error mapping categories for PDF failures:
	- `missing_input`
	- `encrypted_pdf`
	- `corrupted_pdf`
	- `unreadable_pdf`

## Phase 4 Image Resizing Rules

- Image processing uses `Pillow`
- Longest-edge policy: images above `1540` are downscaled while preserving aspect ratio
- Images at or below the limit keep their dimensions unchanged
- Source images outside `im-temp` are copied into `im-temp` with deterministic hashed names
- Rasterized PDF page images already in `im-temp` are resized in place when needed
- Validation rule: post-resize dimensions must be positive and longest edge must be `<= max_longest_edge_px`
