# Implementation Plan: language-model-test-frame-compact

> **Core Objective:** Split every configured LLM prompt into an optional `system_prompt` plus optional `assistant_prompt`, extend configuration to cover `md_mrg.merge_summary`, and add an interactive LLM test panel to the webapp settings page that runs a single-turn chat through the existing workflow job mechanism.

**Traceability:** [Analysis Reference](./language-model-test-frame-compact.plan.analysis.md)

---

## Phase 1: Shared configuration schema and defaults

*Implementing requirements from Analysis Section 2 (`src/common/config.py`, `data/config/settings-default.json`, `src/common/config_dump.py`).*

### Step 1.1: Extend `PromptSettings` and `MdMrgSettings` in `src/common/config.py`
- Replace `summary_prompt_path: Path | None` and `summary_prompt_text: str | None` with:
  - `system_path: str`
  - `system_text: str`
  - `assistant_path: str`
  - `assistant_text: str`
- Update `MdMrgSettings` to carry both `score: PromptSettings` and `summary: PromptSettings`.
- Add `DEFAULT_MERGE_SUMMARY_PROMPT_FILE = Path(__file__).resolve().parents[2] / "data" / "prompts" / "md_mrg_merge_summary_system_prompt.md`.
- If the merge-summary default file does not exist, create `data/prompts/md_mrg_merge_summary_system_prompt.md` with a minimal placeholder system prompt so bootstrap never fails.

### Step 1.2: Rewrite prompt resolution in `src/common/config.py`
- Change `_resolve_prompt_settings(*, field_name, override_path, settings_path_value, default_path)` to accept `system_prompt` and `assistant_prompt` independently.
- For each of the two inputs (override → settings → default for system only):
  - Coerce to `Path` with `_coerce_path`.
  - If coercion yields `None`, treat as empty string.
  - Attempt `read_text(encoding="utf-8")`; on `OSError`/`UnicodeDecodeError`, fall back to empty string.
  - Return the resolved path as a string and the text as a string; never return `None`.
- Assistant prompt is fully optional: missing/empty/unreadable → `("", "")`.
- System prompt uses the default file only when no override or settings path is provided; if the default file is used, emit a `RuntimeWarning` via `_warn_default`.
- Update `_resolve_app_config` to read `md_gen.summary.system_prompt` / `assistant_prompt`, `md_mrg.merge_score.system_prompt` / `assistant_prompt`, and `md_mrg.merge_summary.system_prompt` / `assistant_prompt` (note the on-disk key is `merge_score`, not `score`).
- Construct `MdMrgSettings(score=..., summary=...)`.
- Keep `_coerce_text` for model fields; prompt fields now treat empty string as the missing sentinel.

### Step 1.3: Update `src/common/config_dump.py`
- Change `_append_prompt(lines, section, prompt_path, prompt_text)` to `_append_prompt(lines, section, prompt)` and emit `system_path`, `system_text`, `assistant_path`, and `assistant_text`.
- Add a dump block for `md_mrg.summary`.
- Ensure multiline prompt text remains verbatim.

### Step 1.4: Migrate `data/config/settings-default.json`
- Replace `md_gen.summary.prompt_path` with `system_prompt` and `assistant_prompt`.
- Replace `md_mrg.score` with `md_mrg.merge_score` containing `system_prompt` and `assistant_prompt`.
- Add `md_mrg.merge_summary` with `system_prompt` and `assistant_prompt`.
- Add `temperature` (e.g. `0.7`) under each prompt section to match the shape already used by `settings.json`.
- Keep top-level keys (`source_folder`, `output_folder`, `verbose`, `overwrite`) aligned with `settings.json`.

**Exit Criterion:** `python -c "from common.config import build_config_from_overrides; build_config_from_overrides({}, {})"` loads without error and `AppConfig.md_gen.prompts.system_text` / `assistant_text`, `md_mrg.score.system_text` / `assistant_text`, and `md_mrg.summary.system_text` / `assistant_text` are all strings.

**Validation Command:**
```bash
uv run pytest test/common/test_config.py test/common/test_config_dump.py -v
```

---

## Phase 2: CLI pipeline consumers

*Implementing requirements from Analysis Section 2 (`src/md_gen/foundation.py`, `src/md_gen/summarize.py`, `src/md_mrg/planner.py`, `src/md_mrg/apply.py`) and Section 3 (`llm_cli`).*

### Step 2.1: Update `src/md_gen/foundation.py`
- In `_validate_generation_inputs`, replace the `summary_prompt_text is None` check with `not config.md_gen.prompts.system_text.strip()`.

### Step 2.2: Update `src/md_gen/summarize.py`
- In `summarize_page`, pass `config.md_gen.prompts.system_text` as `system_prompt`.
- Pass `config.md_gen.prompts.assistant_text` as `assistant_prompt` when non-empty, otherwise `""`.

### Step 2.3: Update `src/md_mrg/planner.py`
- In `_validate_plan_inputs`, replace the `summary_prompt_text is None` check with `not cfg.md_mrg.score.system_text.strip()`.
- In `_score_pair`, use `cfg.md_mrg.score.system_text` as the system prompt.

### Step 2.4: Update `src/md_mrg/apply.py`
- In `_validate_apply_inputs`, replace the `summary_prompt_text is None` check with `not cfg.md_gen.prompts.system_text.strip()`.

### Step 2.5: Verify `src/llm_cli/cli.py`
- Confirm `--system` and `--user` are `required=True`, `--assistant` is `default=None`.
- Confirm `main()` builds `Path` objects from CLI args and calls `run_chat` directly without touching `PromptSettings`.
- Confirm missing required arguments cause `argparse` to exit non-zero.

**Exit Criterion:** All CLI modules import successfully and existing unit tests referencing old `summary_prompt_*` fields are updated to `system_*` / `assistant_*`.

**Validation Command:**
```bash
uv run pytest test/md_gen test/md_mrg test/llmcli -v
```

---

## Phase 3: Webapp backend schema and persistence

*Implementing requirements from Analysis Section 2 (`src/webapp/backend/models.py`, `src/webapp/backend/settings_store.py`, `src/webapp/backend/workflow.py`).*

### Step 3.1: Update `src/webapp/backend/models.py`
- Replace `MdGenSummarySettings.prompt_path` with:
  - `system_prompt: str = ""`
  - `assistant_prompt: str = ""`
  - `temperature: float = 0.7`
- Replace `MdMrgScoreSettings.prompt_path` with:
  - `system_prompt: str = ""`
  - `assistant_prompt: str = ""`
  - `temperature: float = 0.7`
- Add `MdMrgSummarySettings` with the same three fields.
- Update `MdMrgSettings` to `score: MdMrgScoreSettings` and `summary: MdMrgSummarySettings`.
- Ensure `AppSettings` still validates `data/config/settings.json` without errors.

### Step 3.2: Update `src/webapp/backend/settings_store.py`
- Rewrite `app_settings_to_shared_overrides(payload)` to emit:
  - `md_gen.summary.system_prompt` / `assistant_prompt`
  - `md_mrg.merge_score.system_prompt` / `assistant_prompt`
  - `md_mrg.merge_summary.system_prompt` / `assistant_prompt`
- Convert empty prompt strings to `None` so the shared loader treats them as missing.

### Step 3.3: Update `src/webapp/backend/workflow.py`
- Update `_settings_to_discovery_config` to build empty `PromptSettings(system_path="", system_text="", assistant_path="", assistant_text="")` for both `md_gen.prompts` and `md_mrg.score`.
- Update `_settings_to_runtime_config`:
  - Read `settings.md_gen.summary.system_prompt` / `assistant_prompt`.
  - Read `settings.md_mrg.score.system_prompt` / `assistant_prompt`.
  - Read `settings.md_mrg.summary.system_prompt` / `assistant_prompt`.
  - Construct `ConfigMdMrgSettings(score=..., summary=...)`.
- Rewrite `_read_prompt(raw_system: str, raw_assistant: str, label: str) -> PromptSettings`:
  - Resolve `raw_system`; if provided but unreadable or empty, raise `WorkflowServiceError(..., status_code=400)`.
  - Resolve `raw_assistant`; if missing/empty/unreadable, yield empty strings without error.
  - Return `PromptSettings(system_path=str(path), system_text=text, assistant_path=..., assistant_text=...)`.

**Exit Criterion:** `uv run pytest test/webapp_tests/test_settings_api.py test/webapp_tests/test_settings_store.py -v` passes with the new schema, including the updated fixture defaults using `system_prompt`/`assistant_prompt` under `merge_score` and adding `merge_summary`.

**Validation Command:**
```bash
uv run pytest test/webapp_tests/test_settings_api.py test/webapp_tests/test_settings_store.py -v
```

---

## Phase 4: LLM test backend job

*Implementing requirements from Analysis Section 2 (`src/webapp/backend/app.py`, `src/webapp/backend/workflow.py`) and Section 3 (error handling, security, performance).*

### Step 4.1: Add shared chat return helper in `src/llm_cli/chat.py`
- Add `run_chat_return_text(config: AppConfig, system: Path, user: Path, assistant: Path | None) -> str`.
- Reuse the existing gateway call logic from `run_chat` but return the response text instead of printing.
- Raise on read/gateway errors so the worker can capture them.
- Keep `run_chat` unchanged for CLI usage (it prints and returns an exit code).

### Step 4.2: Add temp-prompt read/write endpoints in `src/webapp/backend/app.py`
- `GET /api/llm-test-prompt/{name}` reads `data/temp/llm_test_{name}.md` and returns plain text; missing file returns `200` with empty body.
- `PUT /api/llm-test-prompt/{name}` writes the request body to `data/temp/llm_test_{name}.md`, creating `data/temp` if needed.
- Valid `{name}` values are `system`, `user`, `assistant`; reject others with `400`.

### Step 4.3: Add LLM test models and state fields
- In `src/webapp/backend/models.py`, add:
  - `LlmTestResult` with `text: str | None` and `error: WorkflowStatusMessage | None`.
  - `LlmTestRequest` with `system_path: str`, `user_path: str`, `assistant_path: str`, and optional `temperature`, `top_p`, `top_k`, `min_p` overrides.
- Extend `WorkflowState` with `llm_test_status: WorkflowStageStatus = "idle"` and `llm_test_result: LlmTestResult | None = None`.

### Step 4.4: Add `POST /api/workflow/llm-test` endpoint in `src/webapp/backend/app.py`
- Validate `LlmTestRequest`.
- Load settings, resolve shared config.
- Call `workflow_service.start_llm_test(settings, request)`.
- Return the current `WorkflowState`.

### Step 4.5: Extend `WorkflowService` in `src/webapp/backend/workflow.py`
- Add `start_llm_test(self, settings, request) -> WorkflowState`:
  - Check no other stage is running; if so, raise `WorkflowServiceError` with `409`.
  - Set `llm_test_status = "running"`, clear `llm_test_result`, set an info message.
  - Spawn `_run_llm_test_worker` as a daemon thread.
- Add `_run_llm_test_worker(self, config, request)`:
  - Resolve the three paths from `request.system_path`, `request.user_path`, `request.assistant_path`.
  - Apply optional sampling overrides from the request to a copy of `config.language_model`.
  - Call `run_chat_return_text(config, system_path, user_path, assistant_path)`.
  - On success, set `llm_test_status = "complete"` and `llm_test_result.text`.
  - On any exception, set `llm_test_status = "failed"` and `llm_test_result.error` with the error message.
  - Always `_broadcast` the updated state.

**Exit Criterion:** The backend starts, the new endpoints appear in `/docs`, and a mocked gateway call returns a result in `WorkflowState.llm_test_result`.

**Validation Command:**
```bash
uv run pytest test/webapp_tests/test_workflow_api.py -v
```

---

## Phase 5: Frontend settings and LLM test panel

*Implementing requirements from Analysis Section 2 (`src/webapp/frontend/src/types.ts`, `src/webapp/frontend/src/api.ts`, `src/webapp/frontend/src/components/WorkspaceShell.tsx`, `SettingsForm.tsx`, `LlmTestPanel.tsx`, `WorkflowPanel.tsx`).*

### Step 5.1: Update `src/webapp/frontend/src/types.ts`
- Replace `prompt_path` in `MdGenSummarySettings` and `MdMrgScoreSettings` with `system_prompt`, `assistant_prompt`, and `temperature`.
- Add `MdMrgSummarySettings` with the same three fields.
- Update `MdMrgSettings` to `{ score: MdMrgScoreSettings; summary: MdMrgSummarySettings }`.
- Add:
  - `LlmTestRequest` with `system_path`, `user_path`, `assistant_path`, and optional sampling overrides.
  - `LlmTestResult` with `text` and `error` matching the backend model.

### Step 5.2: Update `src/webapp/frontend/src/api.ts`
- Add `fetchLlmTestPrompt(name: 'system' | 'user' | 'assistant'): Promise<string>` using `GET /api/llm-test-prompt/{name}`.
- Add `saveLlmTestPrompt(name, text): Promise<void>` using `PUT /api/llm-test-prompt/{name}` with `Content-Type: text/plain`.
- Add `startLlmTest(request: LlmTestRequest): Promise<WorkflowState>` using `POST /api/workflow/llm-test`.

### Step 5.3: Extract reusable markdown viewer
- Create `src/webapp/frontend/src/components/MarkdownViewer.tsx`.
- Move the `ReactMarkdown` + `SyntaxHighlighter` rendering logic (including the `MARKDOWN_SANITIZE_SCHEMA`, `rehype-sanitize`, code/preview toggle) from `WorkflowPanel.tsx` into this component.
- Props: `content: string`, `mode: 'code' | 'preview'`, optional `className`.
- Update `WorkflowPanel.tsx` to import and use `MarkdownViewer`.

### Step 5.4: Update `src/webapp/frontend/src/components/SettingsForm.tsx`
- Add a "Prompts" section after "Model endpoints" with inputs for:
  - `md_gen.summary.system_prompt`
  - `md_gen.summary.assistant_prompt`
  - `md_mrg.score.system_prompt`
  - `md_mrg.score.assistant_prompt`
  - `md_mrg.summary.system_prompt`
  - `md_mrg.summary.assistant_prompt`
- Keep `updateNested` / `handleChange` working for the new nested shape.

### Step 5.5: Create `src/webapp/frontend/src/components/LlmTestPanel.tsx`
- Accept stable temp file paths: `data/temp/llm_test_system.md`, `data/temp/llm_test_user.md`, `data/temp/llm_test_assistant.md`.
- Local state: `system`, `user`, `assistant` text; `view: 'edit' | 'response'`; `result: LlmTestResult | null`; `error: string` for local write failures.
- On mount, load the three temp files via `fetchLlmTestPrompt`; missing/empty starts empty.
- On text change, debounce (~500 ms) and write via `saveLlmTestPrompt`; surface write errors in a non-fatal banner.
- Layout:
  - Three vertically stacked editor areas using `MarkdownViewer` (code/preview toggle) with inline title rows and no outer frames.
  - Approximate height split: system 30%, user 60%, assistant 10%.
  - System prompt title row has a "Submit" button at the far right.
- On Submit, call `startLlmTest({ system_path, user_path, assistant_path })`, then switch `view` to `'response'`.
- Response view:
  - Reuse `MarkdownViewer` to render `result.text`.
  - Title row with a "Back" button on the far right.
  - If `result.error` is present, show an error banner.
- On Back, switch `view` back to `'edit'` without clearing prompt text.

### Step 5.6: Update `src/webapp/frontend/src/components/WorkspaceShell.tsx`
- For the `settings` section, render a two-column layout:
  - Desktop: `grid-cols-2` with `SettingsForm` on the left and `LlmTestPanel` on the right (50/50).
  - Narrow viewports: stacked (`grid-cols-1`).
- Ensure both panels scroll independently within their columns.

**Exit Criterion:** `npm run build` (or `tsc -b`) in `src/webapp/frontend` passes without type errors and the settings page renders the new two-column layout.

**Validation Command:**
```bash
cd src/webapp/frontend && npm run build
```

---

## Phase 6: Tests and integration verification

*Implementing requirements from Analysis Section 4 (Verification Checklist).*

### Step 6.1: Update Python unit tests
- Update `test/common/test_config.py` to assert `system_path`, `system_text`, `assistant_path`, `assistant_text` and the new `md_mrg.summary` object.
- Update `test/common/test_config_dump.py` to assert the new dump fields and the `md_mrg.summary` section.
- Update `test/md_gen/test_summarize.py`, `test/md_gen/test_foundation.py`, `test/md_mrg/test_mrg_plan.py`, and any other tests that construct `PromptSettings` or reference `summary_prompt_text`.
- Update `test/webapp_tests/test_settings_api.py` and `test/webapp_tests/test_settings_store.py` fixtures to use `system_prompt`/`assistant_prompt` and add `merge_summary`.
- Add tests for `_read_prompt` edge cases: missing assistant file OK, missing/unreadable system file raises `WorkflowServiceError` with `400`.

### Step 6.2: Add LLM test backend tests
- Add tests in `test/webapp_tests/test_workflow_api.py` for:
  - `GET /api/llm-test-prompt/{name}` returns empty text for missing files and persisted text for existing files.
  - `PUT /api/llm-test-prompt/{name}` creates `data/temp` and writes the file.
  - `POST /api/workflow/llm-test` starts a job and returns a `WorkflowState` with `llm_test_status = "running"`.
  - Mock `run_chat_return_text` to verify success/failure states.

### Step 6.3: Run full test suite
- Run pytest with coverage as configured in `pyproject.toml`.
- Address any coverage regressions by adding focused unit tests for the new prompt resolution logic and the LLM test worker.

**Exit Criterion:** All tests pass and coverage meets the project threshold (`--cov-fail-under=80`).

**Validation Command:**
```bash
uv run pytest
```

---

## Implementation Order Summary

1. Phase 1 first — the shared schema change is the foundation for everything else.
2. Phase 2 — update the CLI consumers so `md-gen`, `md-mrg`, and `llm-cli` keep working.
3. Phase 3 — update the webapp backend schemas and adapters.
4. Phase 4 — add the LLM test backend job and temp-file endpoints.
5. Phase 5 — implement the frontend settings split and LLM test panel.
6. Phase 6 — update tests and verify the full suite.

Do not proceed to the next phase until the previous phase's **Validation Command** passes.
