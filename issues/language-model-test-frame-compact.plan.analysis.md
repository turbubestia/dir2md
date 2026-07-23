# Implementation Analysis: language-model-test-frame-compact

## 1. Architectural Impact & Data Flow

This feature touches the shared configuration model, the CLI surface, the webapp settings UI, and the webapp backend job mechanism. The most important structural change is splitting the monolithic `summary_prompt_path`/`summary_prompt_text` pair into separate `system_*` and `assistant_*` prompt fields, and extending prompt configuration to cover `md_mrg.merge_summary` in addition to `md_gen.summary` and `md_mrg.merge_score`.

- **Affected Subsystems:**
  - Shared configuration loader (`src/common/config.py`)
  - Default settings document (`data/config/settings-default.json`)
  - OCR generation pipeline (`src/md_gen`)
  - Merge planning/apply pipeline (`src/md_mrg`)
  - Configuration dump utility (`src/common/config_dump.py`)
  - LLM test CLI (`src/llm_cli`)
  - Webapp backend Pydantic schemas, persistence, and workflow service (`src/webapp/backend`)
  - Webapp frontend settings page and job API (`src/webapp/frontend`)

- **Data Flow Changes:**
  1. `data/config/settings.json` is already using the new schema (`system_prompt`, `assistant_prompt` under `md_gen.summary`, `md_mrg.merge_score`, and `md_mrg.merge_summary`).
  2. `config.py` will read these keys, resolve each optional path, read file contents, and store results as empty strings when missing.
  3. `md_gen` and `md_mrg` consumers switch from `summary_prompt_text` to `system_text` (and, where appropriate, `assistant_text`).
  4. The webapp backend Pydantic models (`AppSettings`, `MdGenSummarySettings`, `MdMrgScoreSettings`) mirror the same shape and persist it atomically.
  5. The frontend settings page is split 50/50: the existing form on the left, a new LLM test panel on the right.
  6. The test panel writes system/user/assistant text to stable files under `data/temp` and dispatches a backend job using the same enqueue/run pattern as OCR/Merge.
  7. The backend job calls the shared LLM chat logic (`llm_cli.chat.run_chat` or equivalent) with the temp file paths, not raw strings.
  8. Job completion updates a response viewer that replaces the prompt editors until the user clicks Back.

## 2. Component & File Impact Map

### `data/config/settings-default.json`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace `md_gen.summary.prompt_path` with `system_prompt` and `assistant_prompt` keys.
  - [ ] Replace `md_mrg.score.prompt_path` with `system_prompt` and `assistant_prompt` keys.
  - [ ] Add `md_mrg.merge_summary` section containing `system_prompt` and `assistant_prompt` keys.
  - [ ] Align top-level legacy keys (`source_folder`, `output_folder`, `verbose`, `overwrite`) with the shape of `settings.json` so both files remain structural mirrors.

### `src/common/config.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace `PromptSettings.summary_prompt_path: Path | None` and `summary_prompt_text: str | None` with `system_path: str`, `system_text: str`, `assistant_path: str`, and `assistant_text: str`.
  - [ ] Update `MdMrgSettings` so it carries both `score: PromptSettings` and a new `summary: PromptSettings` for `merge_summary`.
  - [ ] Add default constants for the merge-summary system prompt path (or reuse existing prompt file).
- **Logic Modifications Required:**
  - [ ] `_resolve_prompt_settings` must accept separate `system_prompt` and `assistant_prompt` inputs, resolve each path independently, read file text when present, and return empty strings when a path is missing/empty/unreadable.
  - [ ] `_resolve_app_config` must read `system_prompt`/`assistant_prompt` from `md_gen.summary`, `md_mrg.merge_score`, and `md_mrg.merge_summary` instead of the legacy `prompt_path` key.
  - [ ] `_resolve_app_config` must construct `MdMrgSettings(score=..., summary=...)`.
  - [ ] `_coerce_text` and path coercion behavior remain, but callers must treat empty string as the missing sentinel.

### `src/common/config_dump.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update `_append_prompt` to accept four display values (`system_path`, `system_text`, `assistant_path`, `assistant_text`) or iterate over them.
  - [ ] Add a dump block for `md_mrg.summary` prompts.

### `src/md_gen/foundation.py`
- **Type of Change:** Modify
- **Logic Modifications Required:**
  - [ ] `_validate_generation_inputs` must check `config.md_gen.prompts.system_text` for emptiness instead of `summary_prompt_text is None`.

### `src/md_gen/summarize.py`
- **Type of Change:** Modify
- **Logic Modifications Required:**
  - [ ] `summarize_page` must pass `config.md_gen.prompts.system_text` as `system_prompt`.
  - [ ] `summarize_page` should pass `config.md_gen.prompts.assistant_text` as `assistant_prompt` when non-empty, otherwise `""`.

### `src/md_mrg/planner.py`
- **Type of Change:** Modify
- **Logic Modifications Required:**
  - [ ] `_validate_plan_inputs` must check `config.md_mrg.score.system_text` for emptiness instead of `summary_prompt_text is None`.

### `src/md_mrg/apply.py`
- **Type of Change:** Modify
- **Logic Modifications Required:**
  - [ ] `_validate_apply_inputs` must check `config.md_gen.prompts.system_text` for emptiness instead of `summary_prompt_text is None`.

### `src/llm_cli/cli.py`
- **Type of Change:** Review / no structural change required
- **Logic Modifications Required:**
  - [ ] Verify that `--system` and `--user` remain `required=True` and `--assistant` remains optional (`default=None`).
  - [ ] Verify that `main()` builds paths from CLI arguments and calls `run_chat` directly, never consulting `PromptSettings`.
  - [ ] Confirm the CLI reports missing arguments via `argparse` and exits non-zero.

### `src/webapp/backend/models.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace `MdGenSummarySettings.prompt_path` with `system_prompt: str` and `assistant_prompt: str`.
  - [ ] Replace `MdMrgScoreSettings.prompt_path` with `system_prompt: str` and `assistant_prompt: str`.
  - [ ] Add `MdMrgSummarySettings` model with `system_prompt: str` and `assistant_prompt: str`.
  - [ ] Update `MdMrgSettings` to contain both `score: MdMrgScoreSettings` and `summary: MdMrgSummarySettings`.

### `src/webapp/backend/settings_store.py`
- **Type of Change:** Modify
- **Logic Modifications Required:**
  - [ ] Update `app_settings_to_shared_overrides` to emit `system_prompt` and `assistant_prompt` for `md_gen.summary`, `md_mrg.merge_score`, and `md_mrg.merge_summary`.
  - [ ] Ensure empty prompt strings are converted to `None` when passed into the shared config loader so the loader treats them as missing.

### `src/webapp/backend/workflow.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add `MdMrgSettings as ConfigMdMrgSettings` already imported; ensure the runtime config builds a `summary` prompt object.
- **Logic Modifications Required:**
  - [ ] `_settings_to_runtime_config` must read `settings.md_gen.summary.system_prompt`/`assistant_prompt` and `settings.md_mrg.score.system_prompt`/`assistant_prompt`.
  - [ ] `_settings_to_runtime_config` must construct `ConfigMdMrgSettings(score=..., summary=...)` from `settings.md_mrg.summary.system_prompt`/`assistant_prompt`.
  - [ ] `_read_prompt` must return a `PromptSettings` populated as `{system_path, system_text, assistant_path, assistant_text}` and must allow empty/missing files to yield empty strings (no error) for optional assistant prompts, while still erroring when a required system prompt path is provided but unreadable/empty.
  - [ ] `_settings_to_discovery_config` should build empty prompt objects with all empty strings.

### `src/webapp/backend/app.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add a new model for LLM test job requests (`LlmTestRequest`) containing the three temp file paths and optionally temperature/top-p/top-k/min-p overrides.
- **Logic Modifications Required:**
  - [ ] Add `POST /api/workflow/llm-test` endpoint that loads settings, resolves the shared config, enqueues/triggers a background job through `WorkflowService`, and returns an initial `WorkflowState`-like status.
  - [ ] Extend `WorkflowService` with `start_llm_test(settings, request)` and a `_run_llm_test_worker(config, system_path, user_path, assistant_path)` that calls `run_chat` (or equivalent shared chat logic) with the resolved paths.
  - [ ] Store the test result (text or error) on the workflow state so the frontend can poll or receive SSE updates.

### `src/webapp/frontend/src/types.ts`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace `prompt_path: string` in `MdGenSummarySettings` and `MdMrgScoreSettings` with `system_prompt: string` and `assistant_prompt: string`.
  - [ ] Add `MdMrgSummarySettings` interface.
  - [ ] Update `MdMrgSettings` to include `score` and `summary`.
  - [ ] Add `LlmTestState`, `LlmTestRequest`, and response-related types if not inferred from `WorkflowState`.

### `src/webapp/frontend/src/api.ts`
- **Type of Change:** Modify
- **Logic Modifications Required:**
  - [ ] Add `startLlmTest(request: LlmTestRequest): Promise<WorkflowState>` that mirrors the OCR/Merge POST pattern.
  - [ ] Add helper to fetch/persist temp prompt files (plain `fetch` with text bodies for `data/temp/llm_test_*.md`).

### `src/webapp/frontend/src/components/WorkspaceShell.tsx`
- **Type of Change:** Modify
- **Logic Modifications Required:**
  - [ ] For the `settings` section, render a two-column layout (50/50 on desktop, stacked on narrow viewports) containing `SettingsForm` and a new `LlmTestPanel`.

### `src/webapp/frontend/src/components/SettingsForm.tsx`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace prompt path inputs under `md_gen.summary` and `md_mrg.score` with `system_prompt` and `assistant_prompt` text inputs.
  - [ ] Add inputs for `md_mrg.summary.system_prompt` and `md_mrg.summary.assistant_prompt`.
- **Logic Modifications Required:**
  - [ ] Update `updateNested`/`handleChange` helpers to modify the new nested shape.

### `src/webapp/frontend/src/components/LlmTestPanel.tsx` (new file)
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Component accepts stable temp file paths and initial text values.
  - [ ] Maintain local state for `system`, `user`, and `assistant` text.
  - [ ] Maintain view mode: `'edit' | 'response'`.
  - [ ] Maintain response/error state.
- **Logic Modifications Required:**
  - [ ] On mount, read `data/temp/llm_test_system.md`, `data/temp/llm_test_user.md`, `data/temp/llm_test_assistant.md` and pre-fill editors; missing/empty files start empty.
  - [ ] On meaningful changes (debounced), write each editor's content to its temp file asynchronously; create `data/temp` if needed; surface errors in the panel without crashing.
  - [ ] Render three vertically stacked areas using the same markdown viewer component/library as `WorkflowPanel` (`ReactMarkdown` + `SyntaxHighlighter`), with title rows inline and no extra frames.
  - [ ] Allocate approximately 30%/60%/10% of the panel height to system/user/assistant editors.
  - [ ] Place the Submit button at the far right of the system prompt title row.
  - [ ] On Submit, dispatch `startLlmTest` with the three temp file paths through the existing job API.
  - [ ] When the job result arrives, switch to a response viewer (reuse the same markdown viewer), hide the editors, and show a Back button in the response viewer title row.
  - [ ] On Back, restore the editor view with unchanged prompt content and hide the response viewer.

### `src/webapp/frontend/src/components/WorkflowPanel.tsx`
- **Type of Change:** Modify (minor)
- **Logic Modifications Required:**
  - [ ] Extract the markdown rendering component (code + preview modes) into a reusable component if it is not already, so `LlmTestPanel` can import it without duplication.

## 3. Boundary & Edge Case Analysis

- **Error Handling:**
  - [ ] Missing or empty prompt paths in `settings.json` must resolve to empty strings in `PromptSettings` without raising.
  - [ ] Unreadable prompt files referenced in `settings.json` must be handled gracefully: if the path is provided but the file cannot be read, the webapp backend should surface a `WorkflowServiceError` with a 400 status; `config.py` should fall back to empty strings rather than crash.
  - [ ] LLM test job failures (gateway errors, timeouts, invalid model config) must be captured and displayed in the response viewer with a Back button available.
  - [ ] Temp file write failures must be surfaced in the panel UI without blocking further edits or submission.

- **Security & Permissions:**
  - [ ] Temp files under `data/temp` are local workspace files; no additional RBAC is required.
  - [ ] The LLM test endpoint reuses the existing CORS and settings-loading path; no new authentication layer is needed.
  - [ ] User-provided prompt text is written to local files and passed to the local LLM gateway; rendered output should still be sanitized through the same `rehype-sanitize` schema used by the workflow markdown viewer.

- **Performance / Scale Impact:**
  - [ ] Temp file writes on every keystroke must be debounced to avoid excessive disk I/O.
  - [ ] The LLM test runs as a single-turn call in a background thread, mirroring OCR/Merge workers, so it does not block the main event loop.
  - [ ] No new database tables or indexes are required; persistence is file-based.

- **Backwards Compatibility:**
  - [ ] The legacy `prompt_path` key is no longer read by `config.py` or the webapp models; `settings-default.json` must be migrated to prevent bootstrap failures.
  - [ ] `llm_cli` remains unchanged in behavior; it was already requiring `--system` and `--user`.

## 4. Verification Checklist

- [ ] `data/config/settings.json` loads without Pydantic/`Field required` errors after model changes.
- [ ] `data/config/settings-default.json` is a structural mirror of `settings.json` and bootstraps successfully.
- [ ] `AppConfig.md_gen.prompts.system_path`/`system_text` and `assistant_path`/`assistant_text` are populated correctly when paths are provided and empty strings when missing.
- [ ] `AppConfig.md_mrg.score` and `AppConfig.md_mrg.summary` both expose `system_*` and `assistant_*` fields.
- [ ] `md_gen` OCR pipeline and `md_mrg` planning/apply pipelines use the new `system_text` fields.
- [ ] `llm_cli` exits non-zero and reports missing arguments when `--system` or `--user` is omitted.
- [ ] `llm_cli` does not reference `PromptSettings` for prompt selection.
- [ ] Webapp settings API GET/PUT round-trips the new prompt schema without validation errors.
- [ ] Settings page renders a 50/50 two-column layout on desktop and a usable stacked layout on narrow viewports.
- [ ] The LLM test panel uses the same markdown viewer component as the OCR workflow.
- [ ] System/user/assistant editors occupy approximately 30%/60%/10% of the right panel height.
- [ ] Submit button is located in the system prompt title row; response viewer has a Back button in its title row.
- [ ] Clicking Submit invokes the model through the existing workflow job mechanism and passes the `data/temp` file paths.
- [ ] `data/temp/llm_test_system.md`, `data/temp/llm_test_user.md`, and `data/temp/llm_test_assistant.md` are created and updated with current editor text.
- [ ] On reload, the editors are pre-filled from the temp files when they exist.
- [ ] Existing unit and integration tests are updated to use the new `PromptSettings` field names and pass.
