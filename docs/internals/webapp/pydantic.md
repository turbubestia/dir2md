# Pydantic

## What It Is

Pydantic is a data validation and serialization library for Python.
You define data schemas as Python classes, and Pydantic:

- validates input data (usually JSON payloads)
- converts values to expected Python types when safe
- provides structured validation errors
- serializes models back to JSON-safe data

This project uses Pydantic v2 style APIs such as `model_validate()` and
`model_dump()`.

## Why It Matters In This Project

The webapp backend receives browser payloads for settings and workflow actions.
Those payloads must be safe and predictable before they reach workflow logic.

Pydantic protects key boundaries:

- API input boundary: request bodies are validated before service calls
- persistence boundary: settings JSON is validated when loading/saving
- response boundary: responses are serialized from known model shapes

Without this layer, malformed input could produce hard-to-debug runtime errors
deep inside OCR/merge flows.

## Where It Lives

Primary schema definitions:

- `src/webapp/backend/models.py`

Main route usage:

- `src/webapp/backend/app.py`

Settings persistence usage:

- `src/webapp/backend/settings_store.py`

## Core Pydantic APIs Used Here

## `BaseModel`

Base class for all schemas. Every major request/response/settings object in
`models.py` inherits from this.

## `Field(...)`

Used to enforce constraints and metadata, for example:

- `min_length=1` for required non-empty strings
- `ge=0.0, le=2.0` for temperature ranges
- defaults such as `verbose: bool = Field(default=False)`

## Constrained and specialized types

The project uses Pydantic types to validate values strictly:

- `AnyHttpUrl` for model endpoint URLs
- `PositiveFloat` for timeout values
- `NonNegativeInt` for retry counts

## `Literal[...]`

Used for finite state values and discriminators, such as:

- workflow stage status (`"idle" | "running" | ...`)
- source/document kinds (`"pdf"`, `"image"`, `"image_group"`)

## `ConfigDict(...)`

Used in two ways:

- `extra="allow"` in editable plan models to preserve unknown keys from
	generated plan data
- `populate_by_name=True` in `MdMrgSettings` to support aliased keys
	(`merge_score` -> `score`, `merge_summary` -> `summary`)

## `model_validate(...)`

Used when validating raw dict payloads manually, especially where custom error
handling is desired.

In `app.py`, some routes accept `payload: dict` and then call
`EditableMergePlan.model_validate(payload)` or
`WorkflowMergeRequest.model_validate(payload)` to return normalized 400 errors.

## `model_dump(mode="json")`

Used before persistence/streaming to produce JSON-safe output.

Examples:

- settings save path serializes `AppSettings` in `settings_store.py`
- SSE workflow events serialize `WorkflowState` in `app.py`

## `@model_validator(mode="after")`

Used for cross-field/cross-item business validation that cannot be expressed by
single-field constraints.

Current example: `EditableMergePlan.reject_duplicate_document_ids` rejects
duplicate document IDs across all plan items.

## Concrete Model Groups In `models.py`

## 1) Settings schema (`AppSettings` and nested models)

Represents the persisted `data/config/settings.json` contract used by the UI.

Highlights:

- `source_folder` and `output_folder` are text fields (existence is not checked
	at schema level)
- endpoint settings require valid HTTP(S) URL, positive timeout, non-negative
	retries
- md_gen and md_mrg sections are strongly typed and bounded

Example valid fragment:

```json
{
	"ocr_model": {
		"endpoint": "http://localhost:8000/v1",
		"model": "llama3.1",
		"timeout_seconds": 30,
		"max_retries": 2
	}
}
```

Example invalid fragment (fails validation):

```json
{
	"ocr_model": {
		"endpoint": "not-a-url",
		"model": "",
		"timeout_seconds": 0,
		"max_retries": -1
	}
}
```

## 2) Workflow discovery/state schemas

These model what the frontend needs to render workflow progress:

- discovery status (`WorkflowDiscoveryResponse`)
- live state (`WorkflowState`)
- list rows (`WorkflowSourceFile`, `WorkflowMergeItem`)
- state messaging (`WorkflowStatusMessage`)

These structures are emitted in both direct API responses and SSE events.

## 3) Editable merge plan schemas

These power the UI editing flow before merge execution.

Important details:

- supports PDF items and grouped image documents
- accepts extra keys to avoid dropping generated metadata
- performs duplicate document ID guard via model validator

## 4) LLM test and preview schemas

- `LlmTestRequest` carries prompt file paths and optional sampling overrides
- `LlmTestResult` and `WorkflowState` surface execution outcome
- `MarkdownPreviewResponse` returns markdown artifact text with identity fields

## Route To Schema Mapping (Concrete Usage)

- `GET /api/settings` -> returns `AppSettings`
- `PUT /api/settings` -> accepts `AppSettings`, returns `AppSettings`
- `POST /api/workflow/start` -> returns `WorkflowDiscoveryResponse`
- `POST /api/workflow/ocr` -> returns `WorkflowState`
- `GET /api/workflow/state` -> returns `WorkflowState`
- `GET /api/workflow/merge-plan` -> returns `EditableMergePlan`
- `PUT /api/workflow/merge-plan` -> validates raw dict as `EditableMergePlan`
- `POST /api/workflow/merge` -> validates raw dict as `WorkflowMergeRequest`
- `GET /api/workflow/merge-results` -> returns `WorkflowMergeResultsResponse`
- `POST /api/workflow/llm-test` -> accepts `LlmTestRequest`, returns
	`WorkflowState`
- `GET /api/workflow/markdown-preview/{artifact_id}` -> returns
	`MarkdownPreviewResponse`
- `GET /api/workflow/merge-result-markdown/{result_id}` -> returns
	`MarkdownPreviewResponse`

## End-To-End Examples

## Example A: Save settings

Request body to `PUT /api/settings`:

```json
{
	"app_name": "dir2md",
	"version": "0.1.0",
	"source_folder": "C:/docs/incoming",
	"output_folder": "C:/docs/out",
	"verbose": false,
	"overwrite": false,
	"ocr_model": {
		"endpoint": "http://localhost:8000/v1",
		"model": "llama3.1",
		"timeout_seconds": 45,
		"max_retries": 2
	},
	"language_model": {
		"endpoint": "http://localhost:8001/v1",
		"model": "llama3.1",
		"timeout_seconds": 45,
		"max_retries": 2
	},
	"md_gen": {
		"summary": {
			"system_prompt": "",
			"assistant_prompt": "",
			"temperature": 0.7
		},
		"image": {
			"max_longest_edge_px": 1600,
			"token_threshold": 4000
		}
	},
	"md_mrg": {
		"merge_score": {
			"system_prompt": "",
			"assistant_prompt": "",
			"temperature": 0.7
		},
		"merge_summary": {
			"system_prompt": "",
			"assistant_prompt": "",
			"temperature": 0.7
		}
	}
}
```

Flow:

1. FastAPI parses body into `AppSettings`.
2. Invalid data returns 422 automatically (for typed route parameters).
3. Valid model is passed to `save_settings(...)`.
4. Store writes `payload.model_dump(mode="json")` atomically.

## Example B: Validate editable merge plan manually

Route `PUT /api/workflow/merge-plan` accepts `payload: dict` then calls
`EditableMergePlan.model_validate(payload)`.

Why this pattern is used here:

- allows custom status code handling for validation errors
- returns `exc.errors(...)` payload as explicit 400 response

Duplicate ID failure example:

```json
{
	"detail": [
		{
			"type": "value_error",
			"msg": "Value error, Duplicate editable plan document id: page_001",
			"loc": []
		}
	]
}
```

## Example C: LLM test run request

Request body to `POST /api/workflow/llm-test`:

```json
{
	"system_path": "C:/Development/projects/dir2md/data/temp/llm_test_system.md",
	"user_path": "C:/Development/projects/dir2md/data/temp/llm_test_user.md",
	"assistant_path": "C:/Development/projects/dir2md/data/temp/llm_test_assistant.md",
	"temperature": 0.6,
	"top_p": 0.9
}
```

Pydantic guarantees the optional sampling fields are typed before workflow code
applies overrides.

## Error Behavior Summary

- Route parameters typed directly as Pydantic models:
	FastAPI returns 422 on validation errors.
- Routes that manually call `model_validate(...)` on dict payloads:
	backend catches `ValidationError` and returns 400 with `detail` list.

Both patterns are used intentionally in `app.py`.

## How To Extend Schemas Safely In This Project

When adding or changing payload fields:

1. Update model(s) in `src/webapp/backend/models.py`.
2. Update route signatures or manual validation paths in
	 `src/webapp/backend/app.py`.
3. If settings shape changed, update mapping logic in
	 `src/webapp/backend/settings_store.py` (especially
	 `app_settings_to_shared_overrides`).
4. Update frontend callers to send/read the new field.
5. Add tests for both valid and invalid payload cases.

Common mistakes to avoid:

- adding a model field but forgetting settings-store mapping
- changing alias keys (`merge_score`, `merge_summary`) without migration
- using overly strict constraints for fields that are intentionally optional or
	staged during UI editing

## When You Should Edit This Documentation

Update this file whenever:

- a backend schema changes
- endpoint request/response contracts change
- validation strategy changes (automatic 422 vs manual 400)
- new examples are needed for frontend or test authors
