# Implementation Analysis: 15-sub1-create-ocr-module

## 1. Architectural Impact & Data Flow

The `md_gen` module is refactored from a batch-stage pipeline (discover → rasterize all → resize all → OCR all → summarize all → persist all) to a per-item tile workflow. In the new workflow, each discovered file is fully processed through rasterize/resize → OCR → page summary → markdown append → metadata capture before the next file begins. This produces one markdown file per source file in a single pass and emits a single `batch.json` describing the entire run.

- **Affected Subsystems:** `src/md_gen` CLI, configuration, discovery, rasterization/resize, OCR, summarization, per-file page processing, batch orchestration, and unit tests.
- **Data Flow Changes:**
  1. CLI parses arguments and builds `AppConfig` (CLI args override `data/config/settings.json`).
  2. Discovery scans the top-level `source` directory, filters supported extensions case-insensitively, and returns a sorted `FileItem` tuple using natural (human) sort.
  3. `foundation.py` iterates over `FileItem`s and invokes `page_processor.process_file` for each.
  4. `page_processor.py` loops through pages (one for images, N for PDFs):
     - Calls `rasterizer.rasterize_page` to obtain a single resized `PIL.Image.Image`.
     - Calls `ocr_processor.extract_markdown` to obtain page markdown text.
     - Calls `summarize.summarize_page` to obtain a page summary.
     - Appends markdown text to the per-file markdown document.
  5. After the last page, `page_processor.py` calls `summarize.summarize_document` to produce the final document summary. **User: this summary is built base on individual page summaries, not the entire text. Then the individual summaries are discarded.**
  6. `page_processor.py` writes the markdown file to the output directory and returns an in-memory metadata dict (WorkItem).
  7. `foundation.py` collects all metadata dicts and writes `batch.json` to the output directory.
  8. On failure, the error is printed, partial markdown is written, the metadata dict is marked `failed`, and processing continues with the next file.

## 2. Component & File Impact Map

### `./src/md_gen/config.py`
- **Type of Change:** Modify (minor alignment).
- **Structural Changes:**
  - [ ] Ensure `read_json_settings_file` creates `data/config/settings.json` from `settings-default.json` when missing (already implemented; verify behavior).
  - [ ] Align default settings key names with code expectations. The current `settings-default.json` uses hyphenated keys (`max-longest-edge-px`, `token-threshold`) while `build_image_settings_from_args` reads underscore keys (`max_longest_edge_px`, `token_threshold`).
- **Logic Modifications Required:**
  - [ ] Verify CLI argument priority is preserved for all settings (CLI value used when not `None`, otherwise JSON value, otherwise hard-coded default).

### `./src/md_gen/discovery.py`
- **Type of Change:** Modify.
- **Structural Changes:**
  - [ ] Update `_ordering_key` to return a natural-sort key so that `file2.pdf` sorts before `file10.pdf`.
  - [ ] Preserve case-insensitive extension matching and top-level-only traversal.
- **Logic Modifications Required:**
  - [ ] Replace simple `path.name.lower()` sort with a natural sort key (e.g., split filename into alphanumeric/integer segments).

### `./src/md_gen/rasterizer.py`
- **Type of Change:** Modify (rewrite).
- **Structural Changes:**
  - [ ] Remove `PdfPageRaster` dataclass and `rasterize_pdf_work_items` batch function.
  - [ ] Introduce a single public function that accepts a `Path`, a `max_edge_size: int`, and an optional `page_number: int`, and returns a `PIL.Image.Image`.
  - [ ] Introduce a helper to return the total page count for a PDF.
  - [ ] Keep typed error class `PdfRasterizationError` (or a renamed generic rasterization error) for unsupported files, missing input, encrypted PDF, corrupted PDF, and unreadable PDF.
- **Logic Modifications Required:**
  - [ ] For PDFs, open the document, render only the requested page, resize the resulting image, close the page/document, and return the resized `PIL.Image.Image`.
  - [ ] For images, open the image, apply EXIF orientation correction, resize to `max_edge_size`, and return the resized `PIL.Image.Image`.
  - [ ] Do not write intermediate image files to disk.
  - [ ] Ensure memory efficiency by not caching the entire PDF or all pages.

### `./src/md_gen/resizer.py`
- **Type of Change:** Delete.
- **Structural Changes:**
  - [ ] Remove file. Its responsibilities are merged into `rasterizer.py`.

### `./src/md_gen/ocr_processor.py`
- **Type of Change:** Modify (rewrite).
- **Structural Changes:**
  - [ ] Remove `SummaryAttempt` dataclass and `execute_summaries` function (summary logic moves to `summarize.py`).
  - [ ] Remove `execute_ocr` batch function that accepted `ImageResizeResult` tuples.
  - [ ] Introduce a pure image-to-text function that accepts a `PIL.Image.Image` and an `AppConfig` (or gateway settings) and returns a markdown string.
- **Logic Modifications Required:**
  - [ ] Encode the image to base64 in memory (e.g., PNG) and send it through `LlamaOcrGateway`.
  - [ ] Perform no file I/O and no summary generation.
  - [ ] Keep deterministic behavior when using deterministic model settings or mocks.

### `./src/md_gen/summarize.py` (new)
- **Type of Change:** Create.
- **Structural Changes:**
  - [ ] Define a public function `summarize_page(config: AppConfig, page_markdown: str) -> str`.
  - [ ] Define a public function `summarize_document(config: AppConfig, page_summaries: list[str]) -> str`.
- **Logic Modifications Required:**
  - [ ] `summarize_page` sends the page markdown to `LlamaLanguageGateway` with the configured system prompt and returns the summary text.
  - [ ] `summarize_document` combines page summaries into a single document summary; if only one page summary exists, return it directly.
  - [ ] Define deterministic behavior for empty OCR results (e.g., return empty summary or a documented placeholder).

### `./src/md_gen/page_processor.py` (new)
- **Type of Change:** Create.
- **Structural Changes:**
  - [ ] Define a public function `process_file(config: AppConfig, file_item: FileItem) -> dict[str, Any]`.
  - [ ] Define an internal metadata dict schema (WorkItem) containing at minimum: `source_file_name`, `file_type`, `page_count`, `date_of_process`, `summary`, `markdown_file`, and `status`.
- **Logic Modifications Required:**
  - [ ] Determine output markdown path as `{source_stem}.md` in `config.paths.output_dir`.
  - [ ] For PDFs, query total page count and loop through pages; for images, process a single page.
  - [ ] For each page:
    - Call `rasterizer.rasterize_page` to get a resized `PIL.Image.Image`.
    - Call `ocr_processor.extract_markdown` to get page markdown.
    - Call `summarize.summarize_page` to get a page summary.
    - Append page markdown to an in-memory buffer.
    - Print `page n done` to the console.
  - [ ] After all pages, call `summarize.summarize_document` to produce the final summary.
  - [ ] Write the accumulated markdown buffer to the output markdown file.
  - [ ] Return the metadata dict with `status` set to `ok`.
  - [ ] On failure, print the error, write any partial markdown accumulated so far, and return the metadata dict with `status` set to `failed`.

### `./src/md_gen/foundation.py`
- **Type of Change:** Modify (rewrite).
- **Structural Changes:**
  - [ ] Remove imports and helpers tied to the old batch stages (`PdfPageRaster`, `ImageResizeResult`, `execute_ocr`, `execute_summaries`, `_collect_images_for_resizing`).
  - [ ] Import `page_processor.process_file` and `discovery.build_work_items`.
- **Logic Modifications Required:**
  - [ ] Ensure output directory exists.
  - [ ] Build work items via `discovery.build_work_items`.
  - [ ] Iterate work items sequentially; for each, print a status line with the source filename and invoke `page_processor.process_file`.
  - [ ] Collect returned metadata dicts into a list.
  - [ ] Write the list as `batch.json` to the output directory.
  - [ ] Continue processing remaining files when one file fails.
  - [ ] Preserve existing error-code exit behavior for config/gateway errors (return codes 2 and 4) and unexpected runtime errors (return code 1).

### `./src/md_gen/markdown_writer.py`
- **Type of Change:** Delete.
- **Structural Changes:**
  - [ ] Remove file. Responsibilities are absorbed by `page_processor.py`.

### `./src/md_gen/metadata_writer.py`
- **Type of Change:** Delete.
- **Structural Changes:**
  - [ ] Remove file. Responsibilities are absorbed by `page_processor.py` and `foundation.py`.

### `./src/md_gen/cli.py`
- **Type of Change:** Modify (minor).
- **Structural Changes:**
  - [ ] No new arguments required; existing arguments already map to `AppConfig`.
- **Logic Modifications Required:**
  - [ ] Verify `build_config_from_args` is called and the resulting config is passed to the updated `foundation.run_foundation_bootstrap`.

### `./test/md_gen/test_rasterizer.py`
- **Type of Change:** Modify (rewrite).
- **Structural Changes:**
  - [ ] Replace tests for `rasterize_pdf_work_items` and `PdfPageRaster` with tests for the new per-page `rasterize_page` function.
  - [ ] Add tests for image resizing through the unified module.
  - [ ] Add tests for unsupported file types and error codes.

### `./test/md_gen/test_resizer.py`
- **Type of Change:** Delete.
- **Structural Changes:**
  - [ ] Remove file. `resizer.py` no longer exists.

### `./test/md_gen/test_ocr_processor.py` (new) / `./test/md_gen/test_markdown_writer.py`, `./test/md_gen/test_metadata_writer.py`
- **Type of Change:** Create / Delete.
- **Structural Changes:**
  - [ ] Delete `test_markdown_writer.py` and `test_metadata_writer.py`.
  - [ ] Create `test_ocr_processor.py` testing pure image-to-text behavior with a mocked gateway.
  - [ ] Create `test_summarize.py` testing page and document summary functions with a mocked language gateway.
  - [ ] Create `test_page_processor.py` testing end-to-end per-file processing for PDFs and images, including failure handling and partial markdown output.

### `./test/md_gen/test_foundation.py`
- **Type of Change:** Modify (rewrite).
- **Structural Changes:**
  - [ ] Replace batch-stage tests with tests for the per-item orchestrator.
  - [ ] Verify `batch.json` is written, markdown files use source stems, and failures continue to the next file.

### `./test/md_gen/test_discovery.py`, `./test/md_gen/test_config.py`
- **Type of Change:** Modify (minor).
- **Structural Changes:**
  - [ ] Add/update tests for natural sort ordering (`file2.pdf` before `file10.pdf`).
  - [ ] Verify case-insensitive extension matching is explicitly tested.
  - [ ] Verify settings key alignment if default JSON keys change.

## 3. Boundary & Edge Case Analysis

- **Error Handling:**
  - Config validation errors (`ConfigValidationError`) and gateway errors (`GatewayError`) continue to propagate to the CLI with existing exit codes (2 and 4).
  - Per-file failures (unreadable PDF, corrupt image, failed OCR/summary) are caught inside `page_processor.process_file`: the error is printed, partial markdown is written, the metadata dict is marked `status=failed`, and `foundation.py` continues with the next file.
  - Unsupported file types discovered by `discovery.py` are skipped with a log line; the new `rasterizer.py` must also raise a clear typed error if called with an unsupported extension.
- **Security & Permissions:**
  - No new network surface beyond the existing OCR and language model gateways.
  - Source directory traversal is restricted to a single level; subdirectories are ignored.
- **Performance / Scale Impact:**
  - The per-item workflow keeps memory bounded: only one page image is held in memory at a time, and no intermediate PNG files are written.
  - PDF documents are opened and closed per `rasterize_page` call (or per file) to avoid holding large documents open for the entire batch.
  - The batch JSON is written once at the end; markdown files are written incrementally per file.
- **Edge Cases:**
  - Empty source directory: `batch.json` contains an empty document list.
  - Single-page PDF or image: document summary equals the single page summary.
  - Multi-page PDF: final summary is generated from collected page summaries.
  - Empty OCR result: summarization behavior must be deterministic and documented.
  - Mixed-case extensions (`.PDF`, `.JPG`) are accepted.
  - Files with numeric suffixes must sort naturally (`file2.pdf` before `file10.pdf`).
  - Output markdown naming conflicts are handled by the existing `overwrite` setting.

## 4. Verification Checklist

- [ ] Verify `data/config/settings.json` is created from defaults when missing and CLI arguments override JSON values.
- [ ] Verify discovery returns files in natural sort order and ignores subdirectories and unsupported extensions.
- [ ] Verify `rasterizer.py` returns a resized `PIL.Image.Image` for both PDF pages and images, raises typed errors for unsupported files, and does not write intermediate images.
- [ ] Verify `ocr_processor.py` returns markdown text from a `PIL.Image.Image` without file I/O or summarization.
- [ ] Verify `summarize.py` produces page summaries and a final document summary, with single-page files using the page summary directly.
- [ ] Verify `page_processor.py` writes one `{source_stem}.md` per file and returns a metadata dict with all required fields.
- [ ] Verify `foundation.py` writes `batch.json` containing metadata dicts in discovery order and continues processing after a failed file.
- [ ] Verify output directory contains exactly N markdown files and 1 `batch.json` after a run with N input files, and no resized/rasterized image files.
- [ ] Verify console output includes `page n done` for each page processed.
- [ ] Verify `md_mrg` files are unchanged.
- [ ] Verify the test suite passes after rewriting/deleting tests for merged or removed modules.
