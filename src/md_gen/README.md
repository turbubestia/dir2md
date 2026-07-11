# md_gen

`src/md_gen` is the ingestion and OCR-preparation module for `dir2md`. It takes a flat directory of source files, converts those files into OCR-ready images, calls the local OCR and summary gateways, and writes deterministic intermediate artifacts that the merge stage can consume later.

This module is intentionally split into small stages. The CLI and configuration layer decides *what* to run and with *which settings*. The rest of the package performs a linear data transformation pipeline:

1. discover source files
2. rasterize PDF pages into images
3. resize all images for OCR
4. estimate image token cost
5. send OCR requests
6. send summary requests
7. persist page markdown
8. persist document metadata

The result is not a final merged document set. `md_gen` produces page-level markdown and document-level metadata in a temp workspace under the chosen output directory.

## What the Module Owns

`md_gen` is responsible for these concerns:

- validating source and output paths
- loading runtime configuration from CLI arguments plus `data/config/settings.json`
- discovering supported source files in one input directory level
- converting PDFs into page images
- normalizing image size before OCR submission
- rejecting images that exceed the configured token budget
- calling the OCR model and the summary model through the shared gateway layer
- writing deterministic markdown and metadata artifacts for downstream processing

It does **not** merge related pages into final documents. That responsibility lives in `src/md_mrg`.

## How to Run It

The project exposes the package as the `md-gen` script defined in `pyproject.toml`.

Typical usage:

```bash
uv run md-gen \
	--source ./data/inbox \
	--output ./data/out
```

Run the pipeline without calling the OCR or summary services:

```bash
uv run md-gen \
	--source ./data/inbox \
	--output ./data/out \
	--dry-run
```

Force markdown and metadata files to be rewritten if they already exist:

```bash
uv run md-gen \
	--source ./data/inbox \
	--output ./data/out \
	--overwrite
```

Use a custom summary prompt file:

```bash
uv run md-gen \
	--source ./data/inbox \
	--output ./data/out \
	--summary-prompt ./data/prompts/md_gen_summary_system_prompt.md
```

## CLI Surface

`cli.py` is now a thin entrypoint. It defines arguments, parses them, calls `build_config_from_args(args)`, and then hands the resulting `AppConfig` to `run_foundation_bootstrap(config)`.

Current command-line arguments:

- `--source`: required existing input directory
- `--output`: required output root, created if missing
- `--summary-prompt`: optional override file for the summary system prompt
- `--ocr-model-endpoint`
- `--ocr-model-name`
- `--ocr-timeout-seconds`
- `--ocr-max-retries`
- `--language-model-endpoint`
- `--language-model-name`
- `--language-timeout-seconds`
- `--language-max-retries`
- `--max-longest-edge-px`
- `--token-threshold`
- `--dry-run`
- `--overwrite`

The CLI does not contain pipeline logic anymore. That logic starts in `foundation.py`.

## Configuration Strategy

`config.py` is now the configuration assembly layer. It builds one `AppConfig` object composed of typed dataclasses:

- `PathSettings`
- `PromptSettings`
- `LlamaModelSettings`
- `ImageSettings`
- `RuntimeSettings`

`build_config_from_args(args)` uses this precedence model:

1. explicit CLI arguments
2. values loaded from `data/config/settings.json`
3. hardcoded defaults for a few optional values

### Settings File

The default settings file is `data/config/settings.json`.

If it does not exist, `read_json_settings_file()` attempts to create it by copying `data/config/settings-default.json` into place and then loading the result.

The current JSON structure expected by `config.py` is:

```json
{
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

### Prompt Loading

`build_prompt_settings_from_args()` resolves the summary prompt in this order:

1. `--summary-prompt`
2. `summary.prompt_path` from `settings.json`
3. builtin prompt text stored in `BUILTIN_SUMMARY_PROMPT`

The current `PromptSettings` dataclass stores both the selected path and the fully loaded prompt text. That means downstream code can either consume prompt text directly or implement additional path-based fallback behavior.

### Model Loading

`build_llama_model_settings_from_args()` is used twice:

- once for the OCR model settings
- once for the language-model summary settings

For each model, endpoint and model name are required from either CLI or JSON. Timeout and retry count fall back to defaults if omitted.

### Path Loading

`build_path_settings_from_args()` currently resolves:

- `source_dir`
- `output_dir`
- `temp_dir = output_dir / "temp"`

This is the new configuration anchor for filesystem paths. The rest of the module should derive any stage-specific directories from this object rather than inventing independent path rules.

## Runtime Data Path

The easiest way to understand `md_gen` is to follow the data through `foundation.py`.

### 1. Bootstrap and directory preparation

`run_foundation_bootstrap(config)` is the orchestration entrypoint.

Its first responsibility is to prepare the output workspace under the configured output root. The pipeline is designed around a temp tree inside the output directory:

- `output/temp/images`
- `output/temp/markdown`
- `output/temp/metadata`

These directories are where the downstream stages read and write their intermediate artifacts.

### 2. Source discovery

`discovery.py` scans only the top level of `config.paths.source_dir`. It does not recurse into nested folders.

Current supported suffixes in code are:

- `.pdf`
- `.png`
- `.jpg`
- `.jpge`

That last suffix is the literal current implementation, so `.jpeg` files are not discovered unless the code is updated.

Discovery returns `WorkItem` records with:

- `source_path`
- `source_type` as either `pdf` or `image`
- `order_index`
- `ordering_key`

Those work items become the canonical ordered input for the rest of the pipeline.

### 3. PDF rasterization

`rasterizer.py` converts each PDF `WorkItem` into one `PdfPageRaster` per page.

Important behavior:

- each page is rendered with `pypdfium2`
- output image names are deterministic and include a short hash derived from the source path
- page metadata preserves original ordering and total page count
- encryption and unreadable PDF failures are classified into explicit error codes

Image source files bypass this stage.

### 4. Image resizing

`resizer.py` receives two kinds of images:

- original image files discovered from the source directory
- page images emitted by the rasterizer

Each image is normalized so its longest edge does not exceed `config.image.max_longest_edge_px`.

Important behavior:

- EXIF orientation is applied before resizing
- unchanged images are copied instead of re-encoded when possible
- output filenames are deterministic and hash-based
- the result object records both original and resized dimensions

### 5. Token budget validation

`token_budget.py` estimates OCR image cost using a simple area-based formula:

```text
estimated_tokens = (width * height) / 1024
```

For each image, the stage emits an `ImageTokenBudgetReport` with:

- resized dimensions
- estimated tokens
- threshold
- warning threshold
- status: `ok`, `warning`, or `error`

If any image exceeds the threshold, `enforce_token_budget()` raises `TokenBudgetValidationError` and the pipeline stops before OCR.

### 6. OCR execution

`execute_ocr()` in `foundation.py` deduplicates resized output image paths, builds OCR requests with `common.gateway.build_default_ocr_requests()`, and sends them through `LlamaOcrGateway`.

Each response is an `OcrResponse` containing:

- the processed image path
- the OCR model name
- the OCR markdown text
- the raw gateway response payload

### 7. Summary execution

`execute_summaries()` uses `LlamaSummaryGateway` to derive a short summary snippet from each OCR markdown block.

This summary is not a replacement for the OCR markdown. It is later used as a lightweight content fingerprint inside metadata fragments.

Each summary attempt records:

- image path
- summary text
- whether the summary failed
- the failure code, if any

Summary failures do not necessarily abort the whole run; they are captured per image.

### 8. Markdown persistence

`markdown_writer.py` writes one markdown file per OCR response into the markdown temp directory.

The writer joins information from multiple prior stages:

- OCR text from `OcrResponse`
- source provenance from `PdfPageRaster`
- original/resized mapping from `ImageResizeResult`
- estimated token usage from `ImageTokenBudgetReport`

The persisted record tells you:

- which source file produced the fragment
- whether that fragment came from an image or a PDF page
- which page index it came from, if any
- which markdown file path was written
- whether the file was skipped because it already existed

For PDFs, output markdown is page-scoped. For standalone images, output markdown is file-scoped.

### 9. Metadata persistence

`metadata_writer.py` groups markdown fragments back by original source file and writes one JSON file per source document.

Each metadata document contains:

- stable `document_id`
- original `source_name`
- `total_pages`
- `is_verified_sequence`
- `fragments`

Each fragment includes:

- page sequence number
- image filename
- markdown filename
- first and last non-empty OCR lines as anchors
- summary text as a snippet fingerprint

For a multi-page PDF, the metadata file describes the ordered page sequence of that PDF. For a standalone image, the metadata file contains a single fragment.

## Output Layout

The intended runtime artifact tree under `--output` is:

```text
output/
	temp/
		images/
			*.png|*.jpg
		markdown/
			*.md
		metadata/
			*.json
```

How those files are used:

- `images/` holds rasterized PDF pages plus OCR-ready image copies or resized variants
- `markdown/` holds page-level OCR text
- `metadata/` holds document-level JSON that `md_mrg` will later consume

## File-by-File Structure

This is the practical ownership map inside `src/md_gen`.

### Entry and configuration

- `cli.py`: command-line entrypoint and error-to-exit-code bridge
- `config.py`: config dataclasses, settings-file loading, path validation, and config assembly
- `foundation.py`: top-level stage orchestration and stage/error logging

### Input normalization

- `discovery.py`: top-level file scanning and `WorkItem` creation
- `rasterizer.py`: PDF page rendering with `pypdfium2`
- `resizer.py`: image normalization for OCR
- `token_budget.py`: image token estimation and hard-stop validation

### Persistence

- `markdown_writer.py`: OCR markdown output files plus per-fragment provenance records
- `metadata_writer.py`: document metadata JSON grouped by original source file

### Support files

- `metadata-schema.json`: schema reference for metadata payload shape
- `__init__.py`: package marker

## Current Refactor Boundary

`cli.py` and `config.py` already reflect the newer configuration strategy: parse arguments once, assemble one typed `AppConfig`, and pass that config into the runtime.

The rest of `md_gen` is partly aligned with that strategy, but there is still a visible seam between the refactored config layer and some downstream assumptions.

The main mismatch to be aware of is this:

- `config.py` currently exposes only `paths.source_dir`, `paths.output_dir`, and `paths.temp_dir`
- `foundation.py` still expects stage-specific path fields such as `im_temp_dir`, `md_temp_dir`, and `metadata_temp_dir`
- `config.py` currently exposes `prompts.summary_prompt_path` and `prompts.summary_prompt_text`
- `foundation.py` still expects `summary_prompt_override_path`, `summary_prompt_default_path`, and `summary_prompt_builtin_text`

So the architectural direction is already clear, but the runtime code is still in a transition state. When updating the remaining files, the easiest approach is to treat `AppConfig` from `config.py` as the source of truth and then make the downstream modules consume that shape consistently.

## How to Follow the Code Path When Updating It

If you want to trace one full run through the package, read the files in this order:

1. `cli.py`
2. `config.py`
3. `foundation.py`
4. `discovery.py`
5. `rasterizer.py`
6. `resizer.py`
7. `token_budget.py`
8. `markdown_writer.py`
9. `metadata_writer.py`

That order matches the runtime data path and makes it easier to update each downstream stage against the refactored config model.