# Consolidated Requirements: Update the Configuration Module
**Status:** LOCKED

## 1. Refinement Journey & Evolution
- **User Intent:** Standardize configuration handling across the shared Python projects so CLI and non-CLI entrypoints resolve settings consistently, while leaving project-specific validation to each consumer.
- **Consolidation Summary:** The request began as a correction to irregular config behavior in `src/common/config.py`. Iteration 2 established the final precedence chain, nullable construction, project-owned validation, per-field warnings, best-effort settings loading, and config-dump traceability. Iteration 3 introduced factory-based construction and sparse override normalization, and Iteration 4 locked the CLI argument-to-config mapping strategy.

## 2. Final Executive Summary
The configuration system must resolve values in a consistent three-tier order: explicit overrides first, then `data/config/settings.json`, then hardcoded defaults. Shared config loading remains responsible for merge behavior and diagnostics, while each project validates its own required inputs and runtime preconditions after resolution.

## 3. Consolidated Requirements & Acceptance Criteria
- **Requirement CFG-001: Deterministic Three-Tier Resolution**
  - **Description:** Every configuration field must resolve in this order: override input, then settings file, then hardcoded default. Fields with no hardcoded default may remain `None` after all sources are exhausted.
  - **Acceptance Criteria:**
    - [ ] Given a field is present in the override input, when configuration is resolved, then that value is used unchanged.
    - [ ] Given a field is absent from the override input but present in settings, when configuration is resolved, then the settings value is used.
    - [ ] Given a field is absent from the override input and settings but has a hardcoded default, when configuration is resolved, then the default value is used.
    - [ ] Given a field is absent from all sources and has no hardcoded default, when configuration is resolved, then the field remains `None`.

- **Requirement CFG-002: Sparse Override Input Contract**
  - **Description:** Entry points must pass only the configuration keys they explicitly own. Omitted optional values must be absent from the override input rather than prefilled with unrelated defaults.
  - **Acceptance Criteria:**
    - [ ] Given a CLI argument is optional and omitted, when the override input is built, then the corresponding key is absent or removed before resolution.
    - [ ] Given a required CLI argument is missing, when parsing runs, then the CLI returns a user-facing error before configuration construction.
    - [ ] Given a non-CLI entrypoint builds configuration, when it constructs overrides, then it passes only the values it explicitly owns.

- **Requirement CFG-003: Project-Owned Post-Resolution Validation**
  - **Description:** The shared configuration module must not enforce project-specific required inputs. Each consuming project must validate required paths and preconditions after config resolution and before work starts.
  - **Acceptance Criteria:**
    - [ ] Given a project does not require a shared path field, when config resolution runs, then resolution does not fail because that field is missing.
    - [ ] Given a project requires an input path, when project validation runs and the field is missing, then the project reports an explicit error and stops.
    - [ ] Given a required input path does not exist, when project validation runs, then the project reports a clear missing-path error.
    - [ ] Given a required output path is not writable, when project validation runs, then the project reports a clear unwritable-path error.

- **Requirement CFG-004: Runtime and Global Option Consistency**
  - **Description:** All global and runtime options must use the same resolution chain in CLI and non-CLI entrypoints.
  - **Acceptance Criteria:**
    - [ ] Given a runtime option is set in settings only, when execution starts without an override, then the settings value is applied.
    - [ ] Given a runtime option is set by CLI override, when execution starts, then the override value takes precedence.
    - [ ] Given a runtime option is absent from both overrides and settings but has a hardcoded default, when execution starts, then the default is applied.
    - [ ] Given the webapp entrypoint resolves runtime options, when it starts, then it uses the same precedence chain as CLI entrypoints.

- **Requirement CFG-005: Per-Field Default Warnings**
  - **Description:** Whenever a field falls back to its hardcoded default, a warning must be emitted for that specific field. No warning should be emitted when a field resolves from overrides or settings.
  - **Acceptance Criteria:**
    - [ ] Given field X falls back to a hardcoded default, when resolution completes, then a warning names field X and its default value.
    - [ ] Given fields X and Y both fall back to defaults, when resolution completes, then two separate warnings are emitted.
    - [ ] Given a field resolves from overrides or settings, when resolution completes, then no warning is emitted for that field.

- **Requirement CFG-006: Best-Effort Settings Loading**
  - **Description:** Settings loading must be resilient and field-oriented. Recognized values are used when valid, unrecognized keys are ignored, and invalid field values are treated as missing without aborting the load.
  - **Acceptance Criteria:**
    - [ ] Given settings contain an unknown key, when settings are loaded, then the key is ignored.
    - [ ] Given a settings field has an unexpected type, when settings are loaded, then that field is skipped and resolution continues.
    - [ ] Given the settings file is absent or unreadable, when settings are loaded, then the system degrades gracefully and treats settings as empty.

- **Requirement CFG-007: Config-Dump Traceability**
  - **Description:** Existing config-dump diagnostics must report the resolved source of each field when verbose or debug mode is active.
  - **Acceptance Criteria:**
    - [ ] Given verbose mode is enabled, when config-dump runs after resolution, then each field identifies whether it came from overrides, settings, or a hardcoded default.

- **Requirement CFG-008: CLI Argument to Config Dict Normalization**
  - **Description:** CLI projects must normalize flat CLI argument names into the nested structure expected by the configuration schema before resolution.
  - **Acceptance Criteria:**
    - [ ] Given `language-model-endpoint`, when the CLI builds overrides, then it normalizes to `{ "language_model": { "endpoint": value } }`.
    - [ ] Given `ocr-model-endpoint`, when the CLI builds overrides, then it normalizes to `{ "ocr_model": { "endpoint": value } }`.
    - [ ] Given `summary-prompt` in `md_gen`, when the CLI builds overrides, then it normalizes to `{ "md_gen": { "summary": { "prompt_path": value } } }`.
    - [ ] Given multiple projects use project-specific domains, when each CLI builds overrides, then the normalization pattern is consistent across projects.
    - [ ] Given normalized overrides are passed to configuration resolution, when settings are merged, then the nested structure aligns with the settings file structure.

## 4. Final Scope & Constraints
- **In-Scope:** Normalize shared configuration merge precedence; support sparse override input; apply project-owned validation after resolution; keep all runtime and global options on the same resolution path; emit one warning per defaulted field; load settings on a best-effort basis; preserve config-dump source tracing; normalize flat CLI names into nested config structures.
- **Out-of-Scope:** Replacing `data/config/settings.json`; introducing schema validation for settings; refactoring OCR, normalization, or merge logic unrelated to configuration; building new UI flows.
- **Technical Constraints & Edge Cases:** `None` means missing and continues the resolution chain; fields without hardcoded defaults may remain `None`; warnings must be per field; settings loading must not fail the whole run because of one bad field; project validation must happen before processing begins; normalization must be deterministic and match the nested settings shape.

**LOCKED**