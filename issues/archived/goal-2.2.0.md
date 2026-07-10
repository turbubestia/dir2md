# Goal 2.2.0 - Implementation Plan for Foundation Dependencies (No Code)

## Purpose
Implement the dependency foundation required for `md-gen` without introducing business logic beyond the minimum needed to connect the pipeline.

This plan follows the decisions locked in Goal 2.1.0:
- PDF rasterization library: `pypdfium2`
- Image processing library: `Pillow`
- Local multimodal gateway payload shape: OpenAI Vision API-compatible request structure
- Concurrency model: sequential
- Dry-run behavior: produce temporary artifacts only, do not write final output
- Overwrite behavior: replace existing outputs when explicitly enabled
- Log format: plain text file output

## Runnable Setup Commands

These commands install the local Python toolchain and the OS packages needed for the planned Python dependencies. They do not install llama.cpp or any model files.

For Ubuntu/Debian-based Linux systems:

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

Create the project package metadata and local environment with `uv`:

```bash
uv init --bare 
uv add pypdfium2 Pillow
uv add --dev pytest
```

If you want a minimal starter `pyproject.toml` before adding packages, create it first with `uv init --bare`, then keep using `uv add` for dependency updates.

If your distribution uses a different package manager, install the equivalent of the Python interpreter, virtual environment support, and image build libraries above.

## Implementation Objectives
- Accept PDFs and image files from a directory, a single file, or a file list.
- Rasterize PDFs into page images.
- Resize images to the LightOnOCR-2 maximum longest edge of 1540 pixels.
- Calculate and validate token usage before OCR submission.
- Send images to a local llama.cpp-backed OCR endpoint.
- Write markdown with provenance metadata into `md-temp`.
- Keep all source files intact and isolate temp artifacts.

## Work Breakdown

### Phase 1 - Project Foundation and Environment
- Confirm Python runtime and `uv` workflow for local execution.
- Define dependency groups for core runtime and test tooling.
- Establish a minimal configuration layer for paths, model endpoint settings, and image limits.
- Decide the final command entry point shape for the first CLI stage.
- Create `pyproject.toml` with `uv init` and record the base runtime/test dependencies.
- Document the exact OS package install commands required for the target Linux platform.

Deliverables:
- environment-ready dependency list
- config model for runtime settings
- CLI entrypoint structure for the `md-gen` foundation

### Phase 2 - File Discovery and Work Item Normalization
- Build input discovery for directories, single files, and explicit file lists.
- Filter supported extensions to PDF and image formats.
- Produce normalized work items with source path, source type, and ordering metadata.
- Preserve deterministic ordering so reruns are stable.

Deliverables:
- source discovery rules
- normalized work-item contract
- deterministic file ordering policy

### Phase 3 - PDF Rasterization Adapter
- Implement PDF-to-image conversion using `pypdfium2`.
- Preserve page order and page index metadata.
- Ensure rasterized output is compatible with the image resizing step.
- Define failure handling for unreadable, encrypted, or corrupted PDFs.

Deliverables:
- PDF rasterization adapter
- page metadata propagation
- PDF error handling strategy

### Phase 4 - Image Resizing Adapter
- Implement image loading and resizing using `Pillow`.
- Enforce the 1540 px longest-edge limit while preserving aspect ratio.
- Keep smaller images unchanged unless a future policy explicitly changes that behavior.
- Make resizing deterministic and safe for OCR input.

Deliverables:
- resize policy implementation
- image dimension reporting
- post-resize validation rules

### Phase 5 - Token Budget Service
- Implement the LightOnOCR-2 token formula from the project requirements.
- Compute estimated tokens from resized image dimensions.
- Validate individual images against the 16k context limit.
- Surface warnings for large images before OCR submission.

Deliverables:
- token estimation service
- threshold validation behavior
- warning/error reporting contract

### Phase 6 - Local LLM Gateway
- Define the request/response contract for llama.cpp OCR calls.
- Use an OpenAI Vision API-compatible shape so multimodal payloads stay structured.
- Keep the gateway isolated behind an interface so OCR and later normalization can share the same transport layer.
- Add timeout, retry, and connection failure handling.

Deliverables:
- llama.cpp gateway adapter
- request/response schema
- timeout and retry policy

### Phase 7 - Markdown Persistence and Metadata
- Write OCR output to `md-temp`.
- Attach the minimum provenance metadata required by later normalization.
- Keep front-matter or header fields stable and machine-readable.
- Track source-to-output mapping for auditability and later cleanup.

Deliverables:
- markdown writer
- metadata header contract
- source/output traceability

### Phase 8 - Artifact Management
- Create and manage temp folders such as `im-temp` and `md-temp`.
- Keep temp outputs separate from final outputs.
- Support dry-run behavior without destructive changes.
- Support explicit overwrite behavior when requested.

Deliverables:
- artifact directory policy
- dry-run/overwrite semantics
- cleanup boundaries

### Phase 9 - Logging and Observability
- Emit plain text logs for each work item and stage.
- Record path, status, and duration for rasterization, resizing, OCR, and persistence.
- Produce a run summary at the end of each invocation.

Deliverables:
- stage-level logging format
- run summary report
- basic failure visibility

### Phase 10 - Validation and Tests
- Add unit tests for token calculation, resize behavior, and ordering rules.
- Add integration tests for PDF rasterization and image processing with fixtures.
- Mock llama.cpp responses so OCR tests are deterministic.
- Validate that temp files are created in the correct locations and source files are preserved.

Deliverables:
- unit test coverage for core utilities
- integration tests for file processing
- deterministic model mocks

## Suggested Dependency Set
Runtime dependencies should cover:
- PDF rendering: `pypdfium2`
- image handling: `Pillow`
- local model HTTP client or transport layer for llama.cpp
- filesystem and path utilities from the standard library
- optional YAML or TOML config support if configuration is externalized early

Test dependencies should cover:
- test runner
- fixture support for sample PDFs and images
- model response mocking

## Configuration Inputs
The implementation should accept configuration for:
- source paths
- output paths
- temp paths
- model endpoint URL and model name
- image size limit
- token threshold
- dry-run flag
- overwrite flag
- logging destination

## Completion Criteria
This goal is complete when:
- PDFs and images can be discovered and normalized into work items.
- PDFs can be rasterized into page images with stable metadata.
- Images are resized to the required OCR limit.
- Token usage can be estimated and validated.
- OCR requests can be sent to a local llama.cpp-backed endpoint.
- Markdown output with provenance metadata is written to `md-temp`.
- Logs and tests cover the critical dependency path.

## Risks and Constraints
- PDF rendering behavior may vary slightly by source document and embedded fonts.
- OCR quality depends on image clarity after resizing, so resizing must remain conservative.
- The OpenAI Vision-compatible payload should stay isolated behind the gateway to avoid leaking protocol details into higher layers.
- Sequential execution is simpler and safer for the first pass, but future scaling may require a worker pool.

## Next Step
After this implementation plan is approved, the next document should translate it into the first concrete implementation slice for the dependency foundation.
