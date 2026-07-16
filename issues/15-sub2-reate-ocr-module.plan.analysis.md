# Implementation Analysis: 15-sub2-reate-ocr-module

## 1. Architectural Impact & Data Flow
*High-level overview of how data flows through the system for this feature. Identify any new patterns or structural additions.*
- **Affected Subsystems:** CLI startup orchestration, configuration presentation, startup diagnostics output, and test coverage for CLI/config rendering.
- **Data Flow Changes:** `md-gen` parses CLI arguments -> resolves `AppConfig` through the existing config builder -> if `--verbose` is present, the CLI emits a structured config dump to standard output -> the dump includes the fully resolved prompt text from `AppConfig.prompts.summary_prompt_text` -> only after that does the CLI call `run_foundation_bootstrap(config)`.
- **Structural Pattern Added:** A presentation-only formatter module is introduced so startup diagnostics stay centralized and the CLI remains a thin orchestration layer.
- **Behavioral Boundary:** The verbose path must not alter config resolution, work-item discovery, OCR, summarization, or exit-code behavior; it only inserts an additional startup print step before bootstrap.

## 2. Component & File Impact Map
*Identify the exact files that must be created, modified, or deleted, and what structural changes they require.*

### `./src/md_gen/cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add a `--verbose` boolean argument to the parser.
  - [ ] Extend the main startup flow so the resolved config can be passed to a dump step before bootstrap.
  - [ ] Keep argument parsing and config resolution as the only responsibilities here; do not add formatting logic directly in the CLI.
- **Logic Modifications Required:**
  - [ ] Gate verbose emission strictly on the new flag.
  - [ ] Ensure the dump is written before `run_foundation_bootstrap(config)` is invoked.
  - [ ] Preserve existing error handling and exit codes for invalid startup paths.

### `./src/md_gen/config_dump.py`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Introduce a dedicated module for rendering resolved `AppConfig` values in a readable structure.
  - [ ] Include all config sections relevant to startup inspection: paths, prompts, OCR model, language model, image settings, and runtime settings.
  - [ ] Represent the effective summary prompt text verbatim, including multi-line content.
- **Logic Modifications Required:**
  - [ ] Provide a single formatting entry point that takes a resolved `AppConfig` and produces the startup dump output.
  - [ ] Preserve readability for long or multi-line prompt text so developers can inspect the exact LLM input.
  - [ ] Keep the module free of bootstrap, file-processing, or config-resolution responsibilities.

### `./test/md_gen/test_cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add coverage for the verbose startup path.
  - [ ] Assert that config dumping happens before the bootstrap flow proceeds.
- **Logic Modifications Required:**
  - [ ] Verify the flag is accepted by the parser.
  - [ ] Verify the dump is emitted only when `--verbose` is present.
  - [ ] Verify the existing non-verbose behavior remains unchanged.

### `./test/md_gen/test_config_dump.py`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Add focused tests for the new formatter module.
  - [ ] Cover the rendering of the prompt text and the main config sections.
- **Logic Modifications Required:**
  - [ ] Verify the formatted output includes the effective summary prompt text exactly as stored in `AppConfig`.
  - [ ] Verify multi-line prompt content remains intact and readable in the dump.

## 3. Boundary & Edge Case Analysis
*Detail how system boundaries, errors, and edge cases will be handled structurally.*
- **Error Handling:** The verbose dump should not introduce new startup failure modes. If config resolution fails, the existing `ConfigValidationError` handling in the CLI remains the first guardrail and should still return the current error code path without attempting to print a config dump.
- **Security & Permissions:** No new permissions or RBAC boundaries are involved. The dump intentionally prints configuration verbatim to standard output because the requirement explicitly requests full visibility for debugging.
- **Performance / Scale Impact:** The added work is a one-time formatting step on startup and should remain trivial relative to OCR or LLM processing. The main caution is avoiding any expensive recomputation of config values; the dump should consume the already resolved `AppConfig`.
- **Output Semantics:** Because the dump goes to standard output only, it should remain visually separated from existing bootstrap stage messages enough that a developer can distinguish startup config from pipeline progress.
- **Prompt Fidelity:** The new module must surface the exact prompt text that will be sent to the LLM, not a path or summary of the source, so the visible dump matches the runtime request payload.

## 4. Verification Checklist
*A concrete list of what needs to be verified during/after implementation to ensure the analysis was correct.*
- [ ] Verify `md-gen --verbose` prints one configuration dump before any bootstrap stage output.
- [ ] Verify `md-gen` without `--verbose` produces the existing startup flow with no config dump.
- [ ] Verify the dump includes the resolved summary prompt text verbatim, including multi-line content.
- [ ] Verify the dump includes all resolved config sections and does not omit runtime values.
- [ ] Verify invalid startup inputs still return the same exit codes and error messages as before.
- [ ] Verify the new formatter module is unit-tested independently from the CLI.
- [ ] Verify the CLI tests still pass for the non-verbose bootstrap path.
