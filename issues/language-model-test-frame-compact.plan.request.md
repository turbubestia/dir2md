# Consolidated Requirements: Language Model Test Panel

**Status:** LOCKED

## 1. Refinement Journey & Evolution

- **User Intent:** Add an interactive language-model test panel to the webapp settings so prompt authors can quickly try different system, user, and assistant prompts in a single-turn chat. Coordinate this with a broader config refactor that splits prompt settings into separate `system_*` and `assistant_*` fields.
- **Consolidation Summary:**
  - Iteration 1 formalized the config refactor, mandatory CLI prompt arguments, and the two-column settings layout, but left open the horizontal split, backend invocation method, Markdown editor choice, response display location, and whether to migrate the default settings file.
  - Iteration 2 resolved the 50/50 split, reuse of the workflow's Markdown viewer, backend invocation through the existing md_gen/md_mrg job mechanism, and migration of `settings-default.json`. The response-display location remained open.
  - Iteration 3 resolved the response display as a replaceable response viewer and added persistence of the three prompt texts to `data/temp` so file paths can be passed to `llm_cli`.

## 2. Final Executive Summary

Refactor the shared `PromptSettings` model and the settings loader in `src/common/config.py` to support separate `system_*` and `assistant_*` prompt fields using empty strings as the missing sentinel. Migrate `settings-default.json` to mirror the new `settings.json` schema. Add a 50/50 two-column settings view in the webapp with a Markdown-aware, single-turn LLM test panel on the right. The panel persists system/user/assistant text to files under `data/temp`, invokes the model through the existing workflow job mechanism, and toggles to a response viewer with a Back button.

## 3. Consolidated Requirements & Acceptance Criteria

- **Requirement CFG-1:** Update `PromptSettings` to expose system and assistant prompt fields
  - **Description:** Replace the current `summary_prompt_path: Path | None` / `summary_prompt_text: str | None` fields in `src/common/config.py` with `system_path: str`, `system_text: str`, `assistant_path: str`, and `assistant_text: str`. Missing values must be represented as empty strings rather than `None`, and callers must test for presence with emptiness checks.
  - **Acceptance Criteria:**
    - [ ] Given an empty or missing prompt path in `settings.json`, when `config.py` builds the settings object, then the corresponding `*_path` field equals `""` and the corresponding `*_text` field equals `""`.
    - [ ] Given a populated prompt path in `settings.json`, when the file is readable, then `system_path`/`assistant_path` contain the resolved path and `system_text`/`assistant_text` contain the file content.
    - [ ] Given any consumer of `PromptSettings`, when it checks for a configured prompt, then it uses an emptiness check (`if not settings.system_path:`) rather than a `None` check.

- **Requirement CFG-2:** Align `config.py` with the current `settings.json` schema
  - **Description:** Update `src/common/config.py` (and any related normalization logic) to read `system_prompt` and `assistant_prompt` from `md_gen.summary`, `md_mrg.merge_score`, and `md_mrg.merge_summary` instead of the legacy `prompt_path` keys. Use `data/config/settings.json` as the source of truth.
  - **Acceptance Criteria:**
    - [ ] Given the current `data/config/settings.json`, when the application loads settings, then no `Field required` validation errors occur.
    - [ ] Given `md_gen.summary.system_prompt` is `"data/prompts/md_gen_summary_system_prompt.md"`, when settings are resolved, then `AppConfig.md_gen.prompts.system_path` points to that file and `system_text` contains its contents.
    - [ ] Given `md_mrg.merge_score.assistant_prompt` is `""`, when settings are resolved, then `AppConfig.md_mrg.score.assistant_path` is `""` and `assistant_text` is `""`.

- **Requirement CFG-3:** Migrate `settings-default.json` to mirror `settings.json`
  - **Description:** Update `data/config/settings-default.json` so its prompt keys match the new `system_prompt`/`assistant_prompt` schema used by `data/config/settings.json`. The two files must remain mirrors of each other in structure.
  - **Acceptance Criteria:**
    - [ ] Given `settings-default.json` is loaded by `config.py`, when schema validation runs, then no `Field required` or `prompt_path` errors occur.
    - [ ] Given both settings files exist, when compared structurally, then they contain the same prompt key names under `md_gen.summary`, `md_mrg.merge_score`, and `md_mrg.merge_summary`.

- **Requirement CLI-1:** Keep mandatory CLI prompt arguments and verify no settings fallback
  - **Description:** Confirm that `src/llm_cli/cli.py` treats `--system`, `--user`, and `--assistant` as required arguments and loads prompt content exclusively from those files. Review the code to ensure no fallback to `PromptSettings` prompt paths remains.
  - **Acceptance Criteria:**
    - [ ] Given `llm_cli` is invoked without any of `--system`, `--user`, or `--assistant`, when argument parsing runs, then the CLI exits with a non-zero status and reports the missing argument(s).
    - [ ] Given `llm_cli` is invoked with all three prompt files, when it runs, then `run_chat` receives the resolved paths/content from the CLI and never reads `PromptSettings` for prompt selection.

- **Requirement WEB-1:** Two-column settings view with 50/50 horizontal split
  - **Description:** Refactor the webapp settings page so the left 50% of the viewport contains the existing settings form and the right 50% contains the new LLM test panel.
  - **Acceptance Criteria:**
    - [ ] Given the settings page loads on a desktop viewport, when rendered, then the settings form occupies approximately 50% of the width and the LLM test panel occupies approximately 50% of the width.
    - [ ] Given the viewport is resized, when the layout responds, then both panels remain usable without overlapping.
    - [ ] Given the viewport is very narrow, when the layout responds, then the panels stack vertically or otherwise remain accessible.

- **Requirement WEB-2:** Markdown-aware single-turn LLM test panel using the workflow's OCR text viewer
  - **Description:** The right-hand panel must contain three vertically stacked markdown editors: system prompt (30% height), user prompt (60% height), and assistant prompt (10% height). Each editor must use the same markdown editor/library currently used to display OCR extracted text in the workflow. Editors must not be wrapped in extra frames, must show their title in the top-left, and the system prompt title row must include a submit button at the far right.
  - **Acceptance Criteria:**
    - [ ] Given the panel is rendered, when inspected, then the system, user, and assistant editor areas consume 30%, 60%, and 10% of the panel height respectively.
    - [ ] Given Markdown content is typed in any editor, when rendered, then Markdown syntax is highlighted using the same component/library as the OCR text viewer.
    - [ ] Given the panel is rendered, when inspected, then each editor shows its title in the top-left of its area with no additional frame surrounding the text edit.
    - [ ] Given the panel is rendered, when inspected, then the submit button is located at the far right of the system prompt title row.
    - [ ] Given the submit button is clicked, when the request is processed, then the configured language model is invoked with the current system, user, and assistant prompt contents as a single-turn chat.

- **Requirement WEB-3:** Display model response in a replaceable response viewer
  - **Description:** After the user clicks Submit, the right-hand panel switches from the three prompt editors to a single response viewer that displays the model output. The system prompt title row's Submit button is replaced by a Back button that restores the three prompt editors. The prompt editors must retain their content while the response is shown so the user can return to them unchanged.
  - **Acceptance Criteria:**
    - [ ] Given the user clicks Submit and the model returns a response, when the UI updates, then the three prompt editors are hidden and a single markdown-aware response viewer occupies the right-hand panel.
    - [ ] Given the response viewer is shown, when inspected, then a Back button is located at the far right of the response viewer's title row.
    - [ ] Given the user clicks Back, when the UI updates, then the three prompt editors reappear with the same system/user/assistant content and the response viewer is hidden.
    - [ ] Given the model call fails, when the UI updates, then the response viewer displays the error and a Back button is available.

- **Requirement WEB-4:** Invoke the language model through the existing workflow job mechanism
  - **Description:** The webapp backend must invoke the LLM test chat using the same job/pipeline mechanism currently used when clicking `OCR` or `Merge` in the workflow. The frontend submit action should enqueue or trigger a backend job that calls into `llm_cli.chat.run_chat` (or equivalent shared logic) rather than spawning a subprocess or adding a separate ad-hoc endpoint.
  - **Acceptance Criteria:**
    - [ ] Given the submit button is clicked, when the frontend dispatches the request, then it uses the same job API/pattern used for md_gen OCR and md_mrg Merge operations.
    - [ ] Given the backend processes the request, when the job runs, then it calls the shared language-model chat logic (e.g., `llm_cli.chat.run_chat`) with the system, user, and assistant prompt contents from the panel.
    - [ ] Given the model call succeeds or fails, when the job completes, then the job status/result is updated so the UI can display the response or error.

- **Requirement WEB-5:** Persist test-panel prompt text to `data/temp`
  - **Description:** The frontend must write the current contents of the system, user, and assistant prompt editors to three separate files under `data/temp` before invoking the backend job (and ideally on every meaningful change). The backend job must pass those file paths to `llm_cli` instead of the prompt text. On startup, if the temp files exist, the frontend must pre-fill the three editors with their contents. Temp file names must be stable (e.g., `data/temp/llm_test_system.md`, `data/temp/llm_test_user.md`, `data/temp/llm_test_assistant.md`).
  - **Acceptance Criteria:**
    - [ ] Given the user edits any prompt, when the frontend persists changes, then the corresponding file under `data/temp` contains the current editor text.
    - [ ] Given the user clicks Submit, when the frontend dispatches the job, then it provides the three `data/temp` file paths as the job inputs.
    - [ ] Given the backend job runs, when it invokes the language model, then it passes the temp file paths to `llm_cli.chat.run_chat` (or equivalent) and does not pass raw prompt text.
    - [ ] Given the application starts and the temp files exist, when the settings page loads, then the three editors are pre-filled with the contents of the temp files.
    - [ ] Given a temp file is missing or empty, when the UI initializes, then the corresponding editor starts empty without raising an error.

## 4. Final Scope & Constraints

- **In-Scope:**
  - Refactoring `PromptSettings` in `src/common/config.py`.
  - Updating settings normalization/loading logic to match the new `settings.json` schema.
  - Migrating `data/config/settings-default.json` to mirror `data/config/settings.json`.
  - Verifying `llm_cli` treats `--system`, `--user`, and `--assistant` as mandatory and has no settings fallback.
  - Restructuring the webapp settings view into a two-column 50/50 layout.
  - Implementing the three-pane markdown-aware LLM test panel in the webapp frontend using the same markdown viewer as the OCR workflow.
  - Toggling the right-hand panel between the three prompt editors and a single response viewer with a Back button.
  - Persisting the three prompt editor contents to files under `data/temp` and pre-filling the editors from those files on startup.
  - Wiring the submit button to invoke the language model through the existing md_gen/md_mrg job mechanism.

- **Out-of-Scope:**
  - Multi-turn chat behavior in the test panel (single-turn only).
  - Persisting test-panel prompt content to `settings.json`.
  - Changing OCR or merge CLI behavior beyond prompt settings loading.

- **Technical Constraints & Edge Cases:**
  - The webapp backend Pydantic models in `src/webapp/backend/models.py` may need schema updates to remain consistent with `config.py`.
  - Empty prompt paths must be handled gracefully without raising file-system errors.
  - The markdown component must remain lightweight and usable offline (same as OCR viewer).
  - The `data/temp` directory must be created automatically if it does not exist.
  - Temp file writes should not block the UI; errors during persistence must be surfaced in the UI without crashing the panel.

**LOCKED**
