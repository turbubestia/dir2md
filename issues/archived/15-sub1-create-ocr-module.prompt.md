# Implementation Plan: 15-sub1-create-ocr-module

> **Core Objective:** Refactor `src/md_gen` from a batch-stage pipeline to a per-item tile workflow: each discovered file is rasterized/resized → OCR'd → page-summarized → written to one `{stem}.md` file, with a single `batch.json` describing the run. Remove obsolete batch modules and rewrite tests accordingly.

---

## Phase 1: Configuration & Settings Alignment

### Step 1.1: Align default settings keys with code expectations
- **Target File:** `./data/config/settings-default.json`
- **Action:** Replace hyphenated top-level keys with the snake-case keys that `config.build_image_settings_from_args` reads.
- **Code Blueprint:**
  ```json
  {
    "app_name": "dir2md",
    "version": "0.1.0",
    "ocr_model": {
      "endpoint": "http://127.0.0.1:8080/v1",
      "model": "lightonocr-2",
      "timeout_seconds": 120,
      "max_retries": 3
    },
    "language_model": {
      "endpoint": "http://127.0.0.1:8081/v1",
      "model": "qwen3-1.7b",
      "timeout_seconds": 120,
      "max_retries": 3
    },
    "summary": {
      "prompt_path": "data/prompts/md_gen_summary_system_prompt.md"
    },
    "image": {
      "max_longest_edge_px": 1540,
      "token_threshold": 4096
    }
  }
  ```

### Step 1.2: Verify CLI-argument priority
- **Target File:** `./src/md_gen/config.py`
- **Action:** Confirm the existing precedence chain is intact: CLI value when not `None` → JSON value → hard-coded default. No logic change is required if the chain is already implemented; only review.
- **Exit Criterion:** `settings-default.json` uses `image.max_longest_edge_px` and `image.token_threshold`, matching `build_image_settings_from_args`.
- **Validation Command:** `uv run pytest test/md_gen/test_config.py -v`

---

## Phase 2: Discovery Natural Sort

### Step 2.1: Implement natural-sort ordering key
- **Target File:** `./src/md_gen/discovery.py`
- **Action:** Replace `_ordering_key` so numeric runs are compared numerically (`file2.pdf` sorts before `file10.pdf`).
- **Code Blueprint:**
  ```python
  import re

  _SPLIT_RE = re.compile(r"(\d+)")

  def _ordering_key(path: Path) -> tuple[str, ...]:
      return tuple(
          int(segment) if segment.isdigit() else segment.lower()
          for segment in _SPLIT_RE.split(path.name)
      )
  ```
- **Exit Criterion:** `file2.pdf` is discovered before `file10.pdf`; case-insensitive matching and top-level-only traversal remain unchanged.
- **Validation Command:** `uv run pytest test/md_gen/test_discovery.py -v`

---

## Phase 3: Rasterizer Rewrite (Merge Resizer)

### Step 3.1: Rewrite `rasterizer.py` for per-page in-memory rasterization
- **Target File:** `./src/md_gen/rasterizer.py`
- **Action:** Delete `PdfPageRaster`, `rasterize_pdf_work_item`, and `rasterize_pdf_work_items`. Add a generic `RasterizationError`, a private resize helper, `rasterize_page(source_path, max_edge_size, page_number=None) -> PIL.Image.Image`, and `get_pdf_page_count(source_path) -> int`.
- **Code Blueprint:**
  ```python
  from __future__ import annotations

  import io
  from pathlib import Path
  from typing import Literal

  from PIL import Image, ImageOps
  import pypdfium2 as pdfium

  RasterizationErrorCode = Literal[
      "unsupported_file",
      "missing_input",
      "encrypted_pdf",
      "corrupted_pdf",
      "unreadable_pdf",
  ]

  class RasterizationError(RuntimeError):
      def __init__(self, source_path: Path, error_code: RasterizationErrorCode, message: str):
          super().__init__(message)
          self.source_path = source_path
          self.error_code = error_code

  _SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

  def _classify_pdfium_error(message: str) -> RasterizationErrorCode: ...

  def _target_dimensions(width: int, height: int, max_longest_edge_px: int) -> tuple[int, int]: ...

  def resize_image(image: Image.Image, max_longest_edge_px: int) -> Image.Image:
      """Return a resized copy; keep original dimensions if already within bounds."""
      ...

  def rasterize_page(source_path: Path, max_edge_size: int, page_number: int | None = None) -> Image.Image:
      """Return a single resized PIL.Image.Image for the requested page (1-based) or the whole image."""
      suffix = source_path.suffix.lower()
      if suffix not in _SUPPORTED_EXTENSIONS:
          raise RasterizationError(source_path, "unsupported_file", f"Unsupported file type: {source_path}")
      if not source_path.exists():
          raise RasterizationError(source_path, "missing_input", f"Source does not exist: {source_path}")
      if suffix == ".pdf":
          # open document, validate page_number, render page, close page/document, resize, return
          ...
      # image branch: open with Image.open, apply ImageOps.exif_transpose, resize, return
      ...

  def get_pdf_page_count(source_path: Path) -> int:
      """Return len(pdfium.PdfDocument(source_path)); close document before returning."""
      ...
  ```

### Step 3.2: Delete obsolete resizer module
- **Target File:** `./src/md_gen/resizer.py`
- **Action:** Remove the file.
- **Exit Criterion:** `rasterizer.py` compiles and `resizer.py` no longer exists.
- **Validation Command:** `uv run pytest test/md_gen/test_rasterizer.py -v`

---

## Phase 4: OCR Processor Rewrite

### Step 4.1: Add in-memory image OCR support to the shared gateway
- **Target File:** `./src/common/gateway.py`
- **Action:** Add `LlamaOcrGateway.send_ocr_request_from_image(image: Image.Image) -> OcrResponse` that encodes the PIL image to PNG bytes, base64-encodes them, and posts the vision payload without touching disk.
- **Code Blueprint:**
  ```python
  import io
  from PIL import Image

  class LlamaOcrGateway(_BaseGateway):
      ...
      def send_ocr_request_from_image(self, image: Image.Image) -> OcrResponse:
          buffer = io.BytesIO()
          image.save(buffer, format="PNG")
          encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
          payload = f"data:image/png;base64,{encoded}"
          messages = [
              {"role": "user", "content": [{"type": "image_url", "image_url": {"url": payload}}]}
          ]
          response = self._post_with_retry(messages)
          response_json = response.json()
          markdown_text = _extract_text_content(response_json)
          return OcrResponse(
              image_path=Path("-"),
              model_name=self._model_name,
              markdown_text=markdown_text,
              raw_response=response_json,
          )
  ```

### Step 4.2: Rewrite `ocr_processor.py` as a pure image-to-text function
- **Target File:** `./src/md_gen/ocr_processor.py`
- **Action:** Remove `SummaryAttempt`, `execute_ocr`, and `execute_summaries`. Keep only `extract_markdown(config: AppConfig, image: Image.Image) -> str`.
- **Code Blueprint:**
  ```python
  from __future__ import annotations

  from typing import TYPE_CHECKING
  from PIL import Image

  from common.gateway import LlamaOcrGateway

  if TYPE_CHECKING:
      from .config import AppConfig

  def extract_markdown(config: AppConfig, image: Image.Image) -> str:
      with LlamaOcrGateway(
          endpoint_url=config.ocr_model.endpoint_url,
          model_name=config.ocr_model.model_name,
      ) as gateway:
          response = gateway.send_ocr_request_from_image(image)
      return response.markdown_text
  ```
- **Exit Criterion:** `ocr_processor.py` performs no file I/O and returns markdown from a PIL image.
- **Validation Command:** `uv run pytest test/md_gen/test_ocr_processor.py -v`

---

## Phase 5: New Summarize Module

### Step 5.1: Create `summarize.py`
- **Target File:** `./src/md_gen/summarize.py`
- **Action:** Implement `summarize_page` and `summarize_document` using `LlamaLanguageGateway` and `TextRequest`.
- **Code Blueprint:**
  ```python
  from __future__ import annotations

  from typing import TYPE_CHECKING

  from common.gateway import LlamaLanguageGateway, TextRequest

  if TYPE_CHECKING:
      from .config import AppConfig

  def summarize_page(config: AppConfig, page_markdown: str) -> str:
      if not page_markdown.strip():
          return ""
      with LlamaLanguageGateway(
          endpoint_url=config.language_model.endpoint_url,
          model_name=config.language_model.model_name,
      ) as gateway:
          response = gateway.send_text_request(
              TextRequest(
                  system_prompt=config.prompts.summary_prompt_text,
                  user_prompt=page_markdown,
              )
          )
      return response.text

  def summarize_document(config: AppConfig, page_summaries: list[str]) -> str:
      cleaned = [s for s in page_summaries if s.strip()]
      if len(cleaned) == 0:
          return ""
      if len(cleaned) == 1:
          return cleaned[0]
      combined = "\n\n".join(cleaned)
      return summarize_page(config, combined)
  ```
- **Exit Criterion:** Page and document summaries are produced; single-page documents reuse the page summary; empty OCR yields an empty summary.
- **Validation Command:** `uv run pytest test/md_gen/test_summarize.py -v`

---

## Phase 6: New Page Processor Module

### Step 6.1: Create `page_processor.py`
- **Target File:** `./src/md_gen/page_processor.py`
- **Action:** Implement `process_file(config, file_item) -> dict[str, Any]` that loops over pages, calls rasterizer/ocr/summarize, accumulates markdown, prints `page n done`, writes `{stem}.md`, and returns a WorkItem metadata dict.
- **Code Blueprint:**
  ```python
  from __future__ import annotations

  from datetime import datetime, timezone
  from pathlib import Path
  from typing import Any

  from .config import AppConfig
  from .discovery import FileItem
  from . import ocr_processor, rasterizer, summarize

  def _build_output_markdown_path(config: AppConfig, file_item: FileItem) -> Path:
      return config.paths.output_dir / f"{file_item.source_path.stem}.md"

  def process_file(config: AppConfig, file_item: FileItem) -> dict[str, Any]:
      output_path = _build_output_markdown_path(config, file_item)
      markdown_buffer: list[str] = []
      page_summaries: list[str] = []
      page_count = 1
      status = "ok"

      try:
          if file_item.source_type == "pdf":
              page_count = rasterizer.get_pdf_page_count(file_item.source_path)
              pages = range(1, page_count + 1)
          else:
              pages = (1,)

          for page_number in pages:
              image = rasterizer.rasterize_page(
                  file_item.source_path,
                  max_edge_size=config.image.max_longest_edge_px,
                  page_number=page_number if file_item.source_type == "pdf" else None,
              )
              page_markdown = ocr_processor.extract_markdown(config, image)
              page_summary = summarize.summarize_page(config, page_markdown)
              markdown_buffer.append(page_markdown)
              page_summaries.append(page_summary)
              print(f"page {page_number} done")
              image.close()

          document_summary = summarize.summarize_document(config, page_summaries)
      except Exception as exc:
          print(f"ERROR processing {file_item.source_path.name}: {exc}")
          document_summary = ""
          status = "failed"

      if output_path.exists() and not config.runtime.overwrite:
          print(f"> skipping file {output_path}: already exists")
      else:
          output_path.write_text("\n\n".join(markdown_buffer).strip() + "\n", encoding="utf-8")

      return {
          "source_file_name": file_item.source_path.name,
          "file_type": file_item.source_type,
          "page_count": page_count,
          "date_of_process": datetime.now(timezone.utc).isoformat(),
          "summary": document_summary,
          "markdown_file": output_path.name,
          "status": status,
      }
  ```
- **Exit Criterion:** One markdown file is written per source file; failures still write partial markdown and return `status=failed`.
- **Validation Command:** `uv run pytest test/md_gen/test_page_processor.py -v`

---

## Phase 7: Foundation Rewrite

### Step 7.1: Rewrite `foundation.py` as a per-item orchestrator
- **Target File:** `./src/md_gen/foundation.py`
- **Action:** Remove all batch-stage helpers and imports. Import `build_work_items` and `process_file`. Ensure output directory exists, iterate work items, collect metadata dicts, and write `batch.json`.
- **Code Blueprint:**
  ```python
  from __future__ import annotations

  import json
  from pathlib import Path

  from common.gateway import GatewayError

  from .config import AppConfig, ConfigValidationError
  from .discovery import build_work_items
  from .page_processor import process_file

  def _emit_stage(stage: str, *, status: str, detail: str = "") -> None:
      detail_token = f" detail={detail}" if detail else ""
      print(f"STAGE name={stage} status={status}{detail_token}")

  def _emit_error(error_code: str, message: str) -> None:
      print(f"ERROR code={error_code} message={message}")

  def run_foundation_bootstrap(config: AppConfig) -> int:
      try:
          config.paths.output_dir.mkdir(parents=True, exist_ok=True)

          work_items = build_work_items(config)
          _emit_stage("discover_work_items", status="ok", detail=f"count={len(work_items)}")

          metadata_records: list[dict] = []
          for file_item in work_items:
              print(f"> processing source {file_item.source_path.name}")
              metadata = process_file(config, file_item)
              metadata_records.append(metadata)

          batch_path = config.paths.output_dir / "batch.json"
          batch_path.write_text(
              json.dumps({"documents": metadata_records}, ensure_ascii=False, indent=2) + "\n",
              encoding="utf-8",
          )
          _emit_stage("persist_batch", status="ok", detail=f"path={batch_path}")

          return 0

      except ConfigValidationError as exc:
          _emit_error(exc.error_code, str(exc))
          return 2
      except GatewayError as exc:
          _emit_error(exc.error_code, str(exc))
          return 4
      except Exception as exc:
          _emit_error("foundation_runtime_error", f"{type(exc).__name__}: {exc}")
          return 1
  ```
- **Exit Criterion:** `batch.json` is written with a `documents` array in discovery order; per-file failures do not stop the batch.
- **Validation Command:** `uv run pytest test/md_gen/test_foundation.py -v`

---

## Phase 8: Remove Deprecated Writers

### Step 8.1: Delete `markdown_writer.py` and `metadata_writer.py`
- **Target Files:** `./src/md_gen/markdown_writer.py`, `./src/md_gen/metadata_writer.py`
- **Action:** Remove both files.
- **Exit Criterion:** Files no longer exist and no active imports reference them.
- **Validation Command:** `uv run python -c "import md_gen.foundation"`

---

## Phase 9: CLI Verification

### Step 9.1: Verify CLI passes config to foundation
- **Target File:** `./src/md_gen/cli.py`
- **Action:** Confirm `build_config_from_args` is called and the resulting `AppConfig` is passed to `run_foundation_bootstrap`. No new arguments are required.
- **Exit Criterion:** `md-gen --source <dir> --output <dir>` runs the new per-item workflow.
- **Validation Command:** `uv run md-gen --source test/fixtures/empty --output tmp/out` (dry-run optional)

---

## Phase 10: Test Suite Rewrite

### Step 10.1: Rewrite `test_rasterizer.py`
- **Target File:** `./test/md_gen/test_rasterizer.py`
- **Action:** Remove `PdfPageRaster` and batch-function tests. Add tests for `rasterize_page` on PDFs and images, unsupported-file errors, missing-input errors, and encrypted/corrupted PDF mapping.

### Step 10.2: Delete `test_resizer.py`
- **Target File:** `./test/md_gen/test_resizer.py`
- **Action:** Remove the file.

### Step 10.3: Delete deprecated writer tests
- **Target Files:** `./test/md_gen/test_markdown_writer.py`, `./test/md_gen/test_metadata_writer.py`
- **Action:** Remove both files.

### Step 10.4: Create `test_ocr_processor.py`
- **Target File:** `./test/md_gen/test_ocr_processor.py`
- **Action:** Mock `LlamaOcrGateway` (or `send_ocr_request_from_image`) and assert `extract_markdown` returns the response text and performs no file I/O.

### Step 10.5: Create `test_summarize.py`
- **Target File:** `./test/md_gen/test_summarize.py`
- **Action:** Mock `LlamaLanguageGateway` and assert `summarize_page` and `summarize_document` behavior, including the single-page shortcut and empty-input handling.

### Step 10.6: Create `test_page_processor.py`
- **Target File:** `./test/md_gen/test_page_processor.py`
- **Action:** Mock `rasterizer`, `ocr_processor`, and `summarize` to test PDF and image flows, failure handling, partial markdown output, and the returned metadata dict schema.

### Step 10.7: Rewrite `test_foundation.py`
- **Target File:** `./test/md_gen/test_foundation.py`
- **Action:** Replace batch-stage tests with tests that verify `batch.json` is written, markdown files use source stems, failures continue to the next file, and existing exit codes (2, 4, 1) are preserved.

### Step 10.8: Update `test_discovery.py` and `test_config.py`
- **Target Files:** `./test/md_gen/test_discovery.py`, `./test/md_gen/test_config.py`
- **Action:** Add/update tests for natural sort (`file2.pdf` before `file10.pdf`) and explicit case-insensitive extension matching. Update config tests if default JSON keys changed.
- **Exit Criterion:** All md_gen tests pass and coverage remains above the configured threshold.
- **Validation Command:** `uv run pytest test/md_gen -v`

---

## Phase 11: Final Integration Verification

### Step 11.1: Run full test suite and inspect artifacts
- **Action:** Execute the complete test suite. Confirm no intermediate image files are produced by the new workflow and that `batch.json` plus one `.md` per input file are the only outputs.
- **Exit Criterion:** `pytest` passes; `md_mrg` source files are untouched; no `resizer`, `markdown_writer`, or `metadata_writer` modules remain.
- **Validation Command:**
  ```bash
  uv run pytest test/md_gen -v
  uv run python -c "import md_gen.rasterizer, md_gen.ocr_processor, md_gen.summarize, md_gen.page_processor, md_gen.foundation"
  ```
