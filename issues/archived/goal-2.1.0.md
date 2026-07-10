# Goal 2.1.0 - Software Architecture for Foundation Dependencies (No Code)

## Scope
Define the architecture needed to satisfy Goal 2.1: establish dependency-level capabilities before implementation.

Focus areas:
- PDF to image extraction
- Image resizing and token-budget safety for LightOnOCR-2
- Local model connectivity through llama.cpp
- Modular boundaries that later support `md-gen`, `md-norm`, `backend`, and `frontend`

This document intentionally excludes implementation details and source code.

## Architectural Principles
- Local-first processing: all inference and file processing run on user machine.
- Layered design: domain workflows depend on interfaces, not concrete tools.
- Replaceable adapters: OCR and text-analysis model providers can change without business logic changes.
- Deterministic file planning: processing paths and output locations are explicit and reproducible.
- Safety by default: preserve source files and isolate temp artifacts.

## Proposed High-Level Architecture

### 1) Interfaces Layer (Contracts)
Provide stable interfaces used by application workflows:
- `document_source_interface`: enumerate accepted files and file metadata.
- `pdf_rasterizer_interface`: convert PDF pages into images.
- `image_preprocessor_interface`: resize/normalize image to model limits.
- `vision_token_budget_interface`: compute and validate image token usage.
- `llm_gateway_interface`: submit prompts/images to local llama.cpp models.
- `markdown_writer_interface`: persist markdown and metadata headers.
- `run_artifact_store_interface`: manage temp folders (`im-temp`, `md-temp`) and lifecycle.

### 2) Application Layer (Use Cases)
No external library logic here; orchestration only:
- `prepare_input_assets_use_case`:
  - Accept source path(s).
  - Detect file types.
  - Produce normalized work items (pdf page/image units).
- `prepare_ocr_images_use_case`:
  - Rasterize PDF pages.
  - Resize all images for model limits.
  - Validate vision token budget.
- `execute_ocr_use_case`:
  - Send preprocessed images to LightOnOCR-2 via llama.cpp.
  - Collect markdown content.
- `persist_markdown_use_case`:
  - Write markdown into `md-temp`.
  - Attach metadata headers with provenance.

### 3) Infrastructure Adapters Layer
Concrete implementations selected at runtime:
- PDF adapter (example options: `pypdfium2`, `PyMuPDF`, `pdf2image` + poppler). **User: prefer `pypdfium2`.**
- Image adapter (example options: `Pillow`, `opencv-python`). **User: prefer `Pillow`**
- Local model adapter for llama.cpp server endpoint.
- Filesystem adapter for path operations and artifact cleanup.

## Dependency Capability Requirements

### PDF Rasterization Capability
Required behavior:
- Input: single PDF or multiple PDFs.
- Output: ordered image pages per PDF.
- Must preserve stable page index metadata.

Adapter expectations:
- Enforce max longest edge = 1540 pixels (LightOnOCR-2 constraint).
- Preserve aspect ratio.
- Deterministic page naming strategy.
- Error mapping for corrupted/locked PDFs.
- Since we produce the image in the right size, we can skip the image preprocessing step.

### Image Preprocessing Capability
Required behavior:
- Enforce max longest edge = 1540 pixels (LightOnOCR-2 constraint).
- Preserve aspect ratio.
- Keep text readability after scaling.

Policy:
- If image exceeds max edge, downscale.
- If image is smaller, keep original unless optional upscaling policy is enabled.

### Vision Token Budget Capability
Use formula from requirements:
- `image_tokens = (width * height) / 1024`

Responsibilities:
- Compute post-resize token usage.
- Validate aggregate request size against context limits.
- Expose warnings when near threshold.

### Local Model Gateway Capability (llama.cpp)
Required behavior:
- Route OCR requests to LightOnOCR-2 endpoint.
- Route normalization requests later to Gemma model endpoint.
- Support model-specific parameters through config.

Contract expectations:
- Unified request/response schema for callers.
- Timeout and retry policy abstraction.
- Structured error categories:
  - connection_error
  - model_unavailable_error
  - invalid_payload_error
  - inference_timeout_error

## Runtime Configuration Model
Central configuration should define:
- source/input paths
- temp/output paths
- rasterization settings
- image limits and token thresholds
- llama.cpp host/port and model identifiers
- retry/timeouts

Configuration should be loadable from CLI args and optional project config file.

## Data Flow (Goal 2.1 Foundation)
1. Input scanner identifies PDFs and image files.
2. PDFs are rasterized into page images.
3. Images pass through preprocessing/resizing.
4. Token budget service validates each image/request.
5. LLM gateway sends OCR requests to LightOnOCR-2.
6. Markdown writer stores outputs plus metadata in `md-temp`.
7. Artifact manager tracks temporary files for later cleanup policy.

## Metadata Contract (Minimum)
Each generated markdown file should include a front-matter header containing at least:
- source_file_name
- source_file_path
- source_type (`pdf_page` or `image`)
- source_page_index (when from PDF)
- generated_at_utc
- model_name
- image_dimensions
- estimated_vision_tokens

This metadata enables Goal 2.2 planning and later `md-norm` grouping.

## Error and Recovery Strategy
- Continue-on-error mode for batch processing should be supported.
- Failed items produce structured failure records without stopping successful items.
- Partial results remain valid and traceable.
- No destructive cleanup on failure paths.

## Observability Requirements
- Structured logs per work item (source, stage, status, duration).
- Run summary metrics:
  - total files scanned
  - pages/images processed
  - successes/failures
  - avg OCR latency
  - total output markdown files

## Compatibility with Future Modules
- `md-gen` will directly use these capabilities.
- `md-norm` will consume metadata and markdown outputs from this architecture.
- `backend` will wrap the same use cases as API endpoints.
- `frontend` will call backend endpoints and render workflow states.

## Decisions Locked for Goal 2.1
- Longest edge hard limit for OCR images: 1540 px.
- Token budget formula: `(w * h) / 1024` after resizing.
- LLM access path: local llama.cpp adapter behind gateway interface.
- Temp directories used by pipeline: `im-temp` and `md-temp`.

## Open Decisions to Resolve in Goal 2.2 (Implementation Plan)
- Final library selection for PDF rasterization. **`pypdfium2`**
- Exact llama.cpp request format and multimodal payload shape. **OpenAI Vision API specification**
- Concurrency model (sequential vs bounded worker pool). **sequential for now**
- Dry-run and overwrite semantics for temp/output folders. **dry-run produces temp, but does not touch output, overwrite replace outputs.**
- Log format (jsonl vs plain text) and retention policy. **Plain text to file**
