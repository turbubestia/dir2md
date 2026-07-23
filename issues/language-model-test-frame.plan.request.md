# Language Model Test Panel

We have added a simple module called `llm_cli` that allows to send custom system, user, and assistant prompt to quickly test which format or prompt styles works. To acomodate for the future use of assistant prompt we need to update the prompt configuration class
```python
class PromptSettings:
    summary_prompt_path: Path | None = None
    summary_prompt_text: str | None = None
```
to be 
```python
class PromptSettings:
    system_path: str
    system_text: str
    assistant_path: str
    assistant_text: str
```
Note we droped the None, and nullitty should be test on emptyness.

The `llm_cli` takes three prompt filename arguments: system, user, and assistant. However, we want to have the flexibility to specify prompt other than those in the setting without changing the settings and for this reason, the prompt must be taken exclusibly from the command line argument as mandatory with no fallback from the settings.

The `llm_cli` work fine from the command line but we want to add it to the web app. The place will be in the settings. Currently the whole screen is devoted to the settings, taking more space than necesary. What we want is to have the left side for the settings and the right for the new panel to test the language model.

The panel for the language model will have a 30% height text edit input for the system prompt, 60% height text edit for the user prompt, and 10% height text edit for the assistant prompt. These three will be markdown text so we want to have markdown text highlighting.

This will act like a single turn chat. Each text edit will have a title on the top left and to the far right of the system prompt a button submit to trigger the call to `llm_cli`.

Don't sorround the tet edit with additional frames.

## Notes:
With the updates we made to the seeting.json schema we broke the config.py, so it must be updated. Use the current setting.json as truth.
```
Settings file at C:\Users\claud\Development\dir2md\data\config\settings.json does not match the expected schema: 2 validation errors for AppSettings md_gen.summary.prompt_path Field required [type=missing, input_value={'system_prompt': 'data/p... '', 'temperature': 0.7}, input_type=dict] For further information visit https://errors.pydantic.dev/2.13/v/missing md_mrg.score Field required [type=missing, input_value={'merge_score': {'system_...'', 'temperature': 0.7}}, input_type=dict] For further information visit https://errors.pydantic.dev/2.13/v/missing
```

---

# Refinement Iteration 1
**Status:** PENDING USER FEEDBACK

## 1. Executive Summary
The request formalizes three coordinated changes: (1) update the shared prompt settings model so each prompt section holds separate system and assistant paths/texts, with emptiness replacing `None` as the "missing" sentinel; (2) make `llm_cli` take all three prompt files exclusively from mandatory command-line arguments with no settings fallback **User: this is already and in place*; and (3) add a markdown-aware LLM test panel to the webapp settings view, splitting the screen into a left-hand settings area and a right-hand test panel.

## 2. Refined Requirements & Acceptance Criteria

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

- **Requirement CFG-3:** Keep the legacy default settings file in scope only if requested
  - **Description:** The current `data/config/settings-default.json` still uses the old `prompt_path` keys. Decide whether it must also be migrated to the new schema.
  - **Acceptance Criteria:**
    - [ ] (Pending user decision) The default settings file is either migrated to the new schema or explicitly excluded from this change.

- **Requirement CLI-1:** Make all three prompt arguments mandatory for `llm_cli`
  - **Description:** Update `src/llm_cli/cli.py` so `--system`, `--user`, and `--assistant` are all required positional or flag arguments. The command must load prompt content exclusively from these CLI-provided files; there must be no fallback to settings-defined prompt paths.
  - **Acceptance Criteria:**
    - [ ] Given `llm_cli` is invoked without any of `--system`, `--user`, or `--assistant`, when argument parsing runs, then the CLI exits with a non-zero status and reports the missing argument(s).
    - [ ] Given `llm_cli` is invoked with all three prompt files, when it runs, then `run_chat` receives the resolved paths/content from the CLI and never reads `PromptSettings` for prompt selection.
    **User: this is already done, but review anyway.**

- **Requirement WEB-1:** Split the webapp settings view into two columns
  - **Description:** Refactor the webapp settings page so the left column contains the existing settings form and the right column contains the new LLM test panel.
  - **Acceptance Criteria:**
    - [ ] Given the settings page loads, when rendered, then the settings form occupies the left side and the LLM test panel occupies the right side.
    - [ ] Given the viewport is resized, when the layout responds, then both panels remain usable without overlapping.

- **Requirement WEB-2:** Add a markdown-aware single-turn LLM test panel
  - **Description:** The right-hand panel must contain three vertically stacked text editors: system prompt (30% height), user prompt (60% height), and assistant prompt (10% height). Each editor must support Markdown syntax highlighting, display a title at the top left, and not be wrapped in extra frames. The system prompt title row must include a submit button at the far right.
  - **Acceptance Criteria:**
    - [ ] Given the panel is rendered, when inspected, then the system, user, and assistant editor areas consume 30%, 60%, and 10% of the panel height respectively.
    - [ ] Given Markdown content is typed in any editor, when rendered, then Markdown syntax is highlighted.
    - [ ] Given the panel is rendered, when inspected, then each editor shows its title in the top-left of its area.
    - [ ] Given the panel is rendered, when inspected, then the submit button is located at the far right of the system prompt title row.
    - [ ] Given the submit button is clicked, when the request is processed, then the configured language model is invoked with the current system, user, and assistant prompt contents as a single-turn chat.

- **Requirement WEB-3:** Decide where and how the model response is displayed
  - **Description:** The current request describes the input panel but does not specify how the model's output is shown to the user.
  - **Acceptance Criteria:**
    - [ ] (Pending user decision) The UI includes a defined area or mechanism for displaying the LLM response and any errors.

## 3. Scope & Constraints

- **In-Scope:**
  - Refactoring `PromptSettings` in `src/common/config.py`.
  - Updating settings normalization/loading logic to match the new `settings.json` schema.
  - Making `--system`, `--user`, and `--assistant` mandatory in `src/llm_cli/cli.py`.
  - Removing any settings-based prompt fallback inside `llm_cli`.
  - Restructuring the webapp settings view into a two-column layout.
  - Implementing the three-pane markdown-aware LLM test panel in the webapp frontend.
  - Wiring the submit button to invoke the language model with the panel contents.

- **Out-of-Scope:**
  - Multi-turn chat behavior in the test panel (single-turn only).
  - Persisting test-panel prompt content to `settings.json`.
  - Changing OCR or merge CLI behavior beyond prompt settings loading.

- **Technical Constraints / Edge Cases:**
  - `settings-default.json` currently uses the legacy `prompt_path` schema and will break if not migrated or explicitly ignored.
  - The webapp backend Pydantic models in `src/webapp/backend/models.py` may also need schema updates to remain consistent with `config.py`.
  - Markdown editor choice affects bundle size and behavior; a lightweight solution is preferred for local/offline use.
  - Empty prompt paths must be handled gracefully without raising file-system errors.

## 4. Open Design Choices (Questions for User)

- **[UX/UI]:** How should horizontal space be split between the settings column and the LLM test panel? (e.g., 50/50, 40/60, a fixed sidebar width?)
- **[UX/UI]:** Where and how should the model's response be displayed? (e.g., a fourth output pane below the prompts, a modal, a collapsible drawer, or inline beneath the submit button?)
**User: 50/50**

- **[Technical]:** How should the webapp backend invoke the language model? (e.g., add a FastAPI endpoint that calls `llm_cli.chat.run_chat`, import and call `run_chat` directly from `app.py`, or spawn the `llm-cli` subprocess?)
**User: should be in the same way as the `md_gen` and `md_mrg` modules when we click in `OCR` and `Merge` in the workflow.**

- **[Technical]:** Do you have a preference for the Markdown editor component? (e.g., Monaco Editor, CodeMirror 6, a lightweight PrismJS-highlighted textarea, or another library?)
**User: Use the same library used in the workflow to show the OCR extracted text.**

- **[Business Logic]:** Should `data/config/settings-default.json` also be migrated to the new `system_prompt`/`assistant_prompt` schema, or should it be left untouched?
**User: yes, settings-default.json must mirror the settings.json.**

---

# Refinement Iteration 2
**Status:** PENDING USER FEEDBACK

## 1. Executive Summary
User feedback resolves the layout split (50/50), the markdown editor choice (same as the OCR workflow viewer), backend invocation pattern (reuse the `md_gen`/`md_mrg` module job pattern), and the default settings file migration. The remaining open item is where and how the model's response should be displayed in the LLM test panel.

## 2. Refined Requirements & Acceptance Criteria

- **Requirement CFG-3:** Migrate `settings-default.json` to the new schema
  - **Description:** Update `data/config/settings-default.json` so its prompt keys match the new `system_prompt`/`assistant_prompt` schema used by `data/config/settings.json`. The two files must remain mirrors of each other in structure.
  - **Acceptance Criteria:**
    - [ ] Given `settings-default.json` is loaded by `config.py`, when schema validation runs, then no `Field required` or `prompt_path` errors occur.
    - [ ] Given both settings files exist, when compared structurally, then they contain the same prompt key names under `md_gen.summary`, `md_mrg.merge_score`, and `md_mrg.merge_summary`.

- **Requirement CLI-1:** Keep mandatory CLI prompt arguments and verify no settings fallback
  - **Description:** Confirm that `src/llm_cli/cli.py` already treats `--system`, `--user`, and `--assistant` as required arguments and loads prompt content exclusively from those files. Review the code to ensure no fallback to `PromptSettings` prompt paths remains.
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

- **Requirement WEB-4:** Invoke the language model through the existing workflow job mechanism
  - **Description:** The webapp backend must invoke the LLM test chat using the same job/pipeline mechanism currently used when clicking `OCR` or `Merge` in the workflow. The frontend submit action should enqueue or trigger a backend job that calls into `llm_cli.chat.run_chat` (or equivalent shared logic) rather than spawning a subprocess or adding a separate ad-hoc endpoint.
  - **Acceptance Criteria:**
    - [ ] Given the submit button is clicked, when the frontend dispatches the request, then it uses the same job API/pattern used for md_gen OCR and md_mrg Merge operations.
    - [ ] Given the backend processes the request, when the job runs, then it calls the shared language-model chat logic (e.g., `llm_cli.chat.run_chat`) with the system, user, and assistant prompt contents from the panel.
    - [ ] Given the model call succeeds or fails, when the job completes, then the job status/result is updated so the UI can display the response or error.

- **Requirement WEB-3:** Display the model response
  - **Description:** The UI must include a defined area or mechanism for displaying the LLM response and any errors.
  - **Acceptance Criteria:**
    - [ ] (Pending user decision) The UI includes a defined area or mechanism for displaying the LLM response and any errors.

## 3. Scope & Constraints

- **In-Scope:**
  - Refactoring `PromptSettings` in `src/common/config.py`.
  - Updating settings normalization/loading logic to match the new `settings.json` schema.
  - Migrating `data/config/settings-default.json` to mirror `data/config/settings.json`.
  - Verifying `llm_cli` treats `--system`, `--user`, and `--assistant` as mandatory and has no settings fallback.
  - Restructuring the webapp settings view into a two-column 50/50 layout.
  - Implementing the three-pane markdown-aware LLM test panel in the webapp frontend using the same markdown viewer as the OCR workflow.
  - Wiring the submit button to invoke the language model through the existing md_gen/md_mrg job mechanism.

- **Out-of-Scope:**
  - Multi-turn chat behavior in the test panel (single-turn only).
  - Persisting test-panel prompt content to `settings.json`.
  - Changing OCR or merge CLI behavior beyond prompt settings loading.

- **Technical Constraints / Edge Cases:**
  - The webapp backend Pydantic models in `src/webapp/backend/models.py` may need schema updates to remain consistent with `config.py`.
  - Empty prompt paths must be handled gracefully without raising file-system errors.
  - The markdown component must remain lightweight and usable offline (same as OCR viewer).

## 4. Open Design Choices (Questions for User)

- **[UX/UI]:** Where and how should the model's response be displayed? (e.g., a fourth output pane below the prompts, replacing the assistant prompt input, a modal, a collapsible drawer, or inline beneath the submit button?)
**User: good question, we can replace the panel with the three text edit with a single one that display the response, and change the submit button by a back button that brings back to the system/user/assistant prompts. This means these three must be persistent on the UI. This brings me to a missing requirement, the text of the three prompts must be written to the three files in a temp folder (let's use `data/temp`), because the llm_cli recived a filepath for the arguments, not the text. This would allow persistance even between session, on start if these temp files exist we can pre-fill the three text edits.**

---

# Refinement Iteration 3
**Status:** LOCKED

## 1. Executive Summary
The user resolved the last open design choice by specifying that the LLM response replaces the three prompt editors with a single response viewer, with a back button returning to the prompt editors. The user also added a persistence requirement: the system, user, and assistant prompt text must be written to files under `data/temp` so the backend job can pass file paths to `llm_cli`, and the UI can pre-fill the three editors from existing temp files on startup.

## 2. Refined Requirements & Acceptance Criteria

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
  - **Description:** Confirm that `src/llm_cli/cli.py` already treats `--system`, `--user`, and `--assistant` as required arguments and loads prompt content exclusively from those files. Review the code to ensure no fallback to `PromptSettings` prompt paths remains.
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

## 3. Scope & Constraints

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

- **Technical Constraints / Edge Cases:**
  - The webapp backend Pydantic models in `src/webapp/backend/models.py` may need schema updates to remain consistent with `config.py`.
  - Empty prompt paths must be handled gracefully without raising file-system errors.
  - The markdown component must remain lightweight and usable offline (same as OCR viewer).
  - The `data/temp` directory must be created automatically if it does not exist.
  - Temp file writes should not block the UI; errors during persistence must be surfaced in the UI without crashing the panel.

**LOCKED**
