# Update the Configuration Module

We implemented in the common project a config.py module for the purpose to share configuration with every other sub project. However, the unification is still not complete with some irregularities. Next I will described the current and expected behaviors.

## Configurations States

1. Currently we give the to config.py the responsability of ensure some configuration values exist, for example, the source or output directories. The issue is not every sub-project will need them. What we need is to be able create a configuration from cli argument as first priority, then fallback to use the `data/config/settings.json`, and the fallback to default values with a warning. This is done for some configurations but it is not normalized. The proper configuration flow is:
    1. The current CLI project configures its own required and optional arguments
    2. the CLI shows the error if any required arguments are missing
    3. It buils a AppConfig with the arguments it has in hand. The AppConfig should allow None for empty parameters
    4. The configuration uses the AppConfig as first priority, for any missing value use those in the settings.json, then any missing in the json use hardcoded default and prompt a warning.
    5. The the CLI review the updated AppConfig to make sure it has all the required information, inputs exist, output can be writen, etc.

2. We have included in the settings.json default values for runtime options like dry-run, verbosity, etc. for cases when there will be no commands like in the UI. Currently some of this values are ignored and are not consistent with CLI arguments and configuration file.

## Goals

- Review the configuration chain to adjust to the expected configuration state and shift propert configuration to the project, not the config.py module.

# Refinement Iteration 1
**Status:** PENDING USER FEEDBACK

## 1. Executive Summary
This change standardizes configuration resolution across all CLI sub-projects so behavior is predictable and shared defaults are applied consistently. The desired model is a clear precedence chain: CLI-provided values first, then `data/config/settings.json`, then hardcoded defaults with warnings for fallback usage. Validation responsibilities should be moved from the shared configuration module to each consuming project so required inputs are enforced only where relevant.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement CFG-001:** Deterministic Configuration Precedence
    - **Description:** Configuration values MUST be resolved in this order for every field: explicit CLI/AppConfig value, then settings file value, then hardcoded default value. Missing values filled from defaults MUST emit a warning.
    - **Acceptance Criteria:**
        - [ ] Given a field is provided by CLI/AppConfig, When configuration is resolved, Then that field value is preserved and neither settings nor hardcoded default overrides it.
        - [ ] Given a field is missing in CLI/AppConfig but present in settings, When configuration is resolved, Then the settings value is used.
        - [ ] Given a field is missing in both CLI/AppConfig and settings, When configuration is resolved, Then the hardcoded default is used and a warning is produced.

- **Requirement CFG-002:** Nullable AppConfig Construction
    - **Description:** Each CLI project MUST construct an AppConfig from parsed arguments, allowing `None` for omitted optional values so downstream resolution can fill them.
    - **Acceptance Criteria:**
        - [ ] Given optional CLI arguments are omitted, When the CLI builds AppConfig, Then corresponding AppConfig fields are `None` rather than prefilled with unrelated defaults.
        - [ ] Given required CLI arguments are missing, When argument parsing runs, Then the CLI returns a user-facing error before task execution starts.

- **Requirement CFG-003:** Project-Owned Validation
    - **Description:** Shared config resolution MUST not enforce project-specific required paths or runtime preconditions. Each project (for example `md_gen`, `md_mrg`, webapp entrypoints) MUST validate required inputs/outputs after merged config is produced.
    - **Acceptance Criteria:**
        - [ ] Given a project does not need `source_folder` or `output_folder`, When shared config resolution runs, Then it does not fail solely due to those missing values.
        - [ ] Given a project requires input/output paths, When post-resolution validation runs in that project, Then it reports missing paths, non-existent required inputs, or non-writable outputs with explicit errors.

- **Requirement CFG-004:** Runtime Option Consistency
    - **Description:** Runtime options defined in settings (for example dry-run and verbosity) MUST be consistently recognized by all execution entrypoints, including CLI and non-CLI contexts.
    - **Acceptance Criteria:**
        - [ ] Given runtime options are set only in settings, When execution starts without overriding CLI flags, Then runtime behavior reflects the settings values.
        - [ ] Given runtime options are provided via CLI flags, When execution starts, Then CLI values override settings values for those options.

- **Requirement CFG-005:** Warning and Diagnostics Behavior
    - **Description:** Fallback and merge decisions MUST be observable via consistent warning and diagnostics output to support debugging and configuration audits.
    - **Acceptance Criteria:**
        - [ ] Given at least one field is filled by hardcoded default, When config resolution completes, Then a warning identifies the field(s) that used defaults.
        - [ ] Given verbose/debug mode is enabled, When config is resolved, Then the resolved source per field (CLI, settings, default) can be inspected through existing config-dump diagnostics.

## 3. Scope & Constraints
- **In-Scope:**
    - Normalize merge precedence and fallback semantics in shared configuration loading.
    - Ensure CLI constructors produce nullable AppConfig objects and defer final validation to project modules.
    - Align dry-run/verbosity behavior between CLI arguments and settings-based execution.
    - Standardize warning behavior when hardcoded defaults are used.
- **Out-of-Scope:**
    - Replacing existing configuration storage format (`data/config/settings.json`) with a new system.
    - Building new UX flows unrelated to configuration merge/validation behavior.
    - Refactoring unrelated OCR/merge processing logic.
- **Technical Constraints / Edge Cases:**
    - Distinguish between an omitted value and an explicitly provided empty value from CLI.
    - Preserve backward compatibility for existing CLI commands and tests where behavior is not intentionally changed.
    - Validation order must prevent runtime work from starting when required project-specific resources are invalid.
    - Warnings should avoid noisy duplication when multiple fields fallback in a single run.

## 4. Open Design Choices (Questions for User)
- **[Business Logic]:** For fields set to `None` explicitly in AppConfig, should `None` always mean "missing, continue fallback chain," or should any fields treat explicit `None` as "intentionally unset" and stop fallback?
**User: None value means missing and should follow the resolution chain. Some fields like user defined path if missing in the json setting will remain None since there is no hardcoded default. But then it is responsability of the consumer check every mandatory fields for its execution project are present. It is not responsability of the config.py module ensure not none field, unles there can be a hardcoded default value.**

- **[Technical]:** Should fallback warnings be emitted once per missing field, or as a single aggregated warning message per run?
**User: one warning for every missing field so the user know what needs to be added.**

- **[Technical]:** Which runtime options must be guaranteed consistent immediately (only `dry_run` and `verbosity`, or a broader list)?
**User: all the global and runtime options.**

- **[Technical]:** Do you want a strict schema validation step for `settings.json` (type/range checks) before merge, or only best-effort field-level fallback?
**User: for now no schema, best-effor field-level.**

# Refinement Iteration 2
**Status:** OPENED

## 1. Executive Summary
All open design questions are now resolved. This iteration locks the requirements, incorporating user clarifications: `None` in AppConfig always means "missing value, continue resolution chain"; per-field warnings are emitted individually; all global and runtime options (not just `dry_run`/`verbosity`) must be consistently resolved; and settings loading uses best-effort field-level fallback with no schema validation. The shared `config.py` module is responsible only for fields with hardcoded defaults — user-defined paths with no default legitimately remain `None`, and each consuming project validates what it requires.

## 2. Refined Requirements & Acceptance Criteria

- **Requirement CFG-001:** Deterministic Configuration Precedence
    - **Description:** Every AppConfig field MUST be resolved in this strict order: (1) CLI/AppConfig-provided value, (2) `data/config/settings.json` value, (3) hardcoded default. `None` in AppConfig always means "not provided" and triggers continuation down the chain. Fields with no hardcoded default stay `None` after exhausting all sources.
    - **Acceptance Criteria:**
        - [ ] Given a field is non-None in AppConfig, When configuration is resolved, Then that value is used unchanged; settings and hardcoded defaults are not consulted for that field.
        - [ ] Given a field is `None` in AppConfig but present in settings, When configuration is resolved, Then the settings value is used for that field.
        - [ ] Given a field is `None` in AppConfig and absent from settings but has a hardcoded default, When configuration is resolved, Then the hardcoded default is used and a per-field warning is emitted.
        - [ ] Given a field is `None` in AppConfig, absent from settings, and has no hardcoded default, When configuration is resolved, Then the field remains `None` after resolution with no warning emitted.

- **Requirement CFG-002:** Nullable AppConfig Construction
    - **Description:** Each CLI project MUST construct an AppConfig using only the arguments it explicitly parsed, setting unspecified optional fields to `None`. No pre-filling with unrelated defaults at construction time.
    - **Acceptance Criteria:**
        - [ ] Given optional CLI arguments are omitted, When the CLI builds AppConfig, Then corresponding AppConfig fields are `None`.
        - [ ] Given required CLI arguments are missing, When argument parsing runs, Then the CLI returns a user-facing error before any AppConfig is constructed or task execution begins.

- **Requirement CFG-003:** Project-Owned Post-Resolution Validation
    - **Description:** The shared `config.py` module MUST NOT enforce any project-specific required fields. After receiving the merged AppConfig, each project (e.g., `md_gen`, `md_mrg`, webapp entrypoints) MUST perform its own validation of mandatory fields before starting work.
    - **Acceptance Criteria:**
        - [ ] Given a project does not require `source_folder`, When shared config resolution runs, Then resolution does not fail due to `source_folder` being `None`.
        - [ ] Given a project requires `source_folder`, When the project's post-resolution validation runs and `source_folder` is `None`, Then the project emits an explicit user-facing error and halts before performing any processing.
        - [ ] Given required input paths are non-None but do not exist on disk, When project validation runs, Then a clear error is reported identifying the missing path.
        - [ ] Given required output paths are non-None but are not writable, When project validation runs, Then a clear error is reported identifying the path.

- **Requirement CFG-004:** All Runtime and Global Options Consistently Resolved
    - **Description:** Every global and runtime option (including but not limited to `dry_run`, `verbosity`, log level, and any future global flags) MUST flow through the same three-tier resolution chain. No runtime option may bypass or short-circuit this chain.
    - **Acceptance Criteria:**
        - [ ] Given a runtime option is set in settings only, When execution starts without a CLI override, Then the settings value is applied.
        - [ ] Given a runtime option is provided via CLI flag, When execution starts, Then the CLI value overrides the settings value for that option.
        - [ ] Given a runtime option is absent from both CLI and settings but has a hardcoded default, When execution starts, Then the hardcoded default is applied and a per-field warning is emitted.
        - [ ] Given execution runs through the webapp (non-CLI) entrypoint, When runtime options are resolved, Then they follow the same chain using settings as the primary source.

- **Requirement CFG-005:** Per-Field Warning on Hardcoded Default Fallback
    - **Description:** Whenever a field falls back to its hardcoded default (tier 3), a distinct warning MUST be emitted for that specific field, naming it explicitly. Warnings are NOT emitted for fields that correctly resolve from CLI or settings.
    - **Acceptance Criteria:**
        - [ ] Given field `X` falls back to hardcoded default, When config resolution completes, Then a warning is logged in the form: `"Config field 'X' not set; using default value: <value>"` (or equivalent).
        - [ ] Given fields `X` and `Y` both fall back to hardcoded defaults, When config resolution completes, Then two separate warnings are emitted, one per field.
        - [ ] Given a field resolves from CLI or settings, When config resolution completes, Then no warning is emitted for that field.

- **Requirement CFG-006:** Best-Effort Field-Level Settings Loading
    - **Description:** When reading `data/config/settings.json`, the loader MUST apply a best-effort field-level strategy: recognized fields are extracted and used; unrecognized fields are ignored; type mismatches on individual fields are treated as missing (field is skipped) without aborting the entire load.
    - **Acceptance Criteria:**
        - [ ] Given `settings.json` contains an unrecognized key, When settings are loaded, Then the unknown key is ignored and loading continues.
        - [ ] Given a field in `settings.json` has an unexpected type, When settings are loaded, Then that field is treated as absent and the resolution chain proceeds to the next tier.
        - [ ] Given `settings.json` is absent or unreadable, When settings are loaded, Then loading degrades gracefully (all settings fields treated as absent) without raising an unhandled exception.

- **Requirement CFG-007:** Config-Dump Diagnostics Traceability
    - **Description:** The existing config-dump diagnostics MUST report the resolved source (CLI, settings, or hardcoded default) for each field when verbose/debug mode is active.
    - **Acceptance Criteria:**
        - [ ] Given verbose mode is enabled, When config-dump runs after resolution, Then each field entry indicates which tier supplied its value.

## 3. Scope & Constraints
- **In-Scope:**
    - Normalize three-tier merge precedence and fallback semantics in `config.py`.
    - Update all CLI projects (`md_gen`, `md_mrg`) to construct nullable AppConfig from parsed arguments only.
    - Move project-specific path and precondition validation out of `config.py` into each consuming project.
    - Ensure all global and runtime options (not just `dry_run`/`verbosity`) follow the resolution chain.
    - Emit one warning per field that falls back to a hardcoded default.
    - Apply best-effort field-level loading from `settings.json`.
    - Update config-dump diagnostics to show resolution source per field in verbose mode.
- **Out-of-Scope:**
    - Replacing `data/config/settings.json` with a different configuration format or storage system.
    - Adding schema validation or type enforcement for `settings.json`.
    - Refactoring OCR, normalization, or merging processing logic unrelated to configuration.
    - Building new UI flows.
- **Technical Constraints / Edge Cases:**
    - `None` in AppConfig always means "not provided" — there is no mechanism for "intentionally unset" that halts the chain.
    - Fields without a hardcoded default legitimately remain `None`; no warning is issued in that case.
    - Backward compatibility must be preserved for existing CLI commands and tests where behavior is not intentionally changing.
    - Post-resolution project validation must run before any I/O or processing work begins, preventing partial execution with invalid configuration.
    - Per-field warnings must not duplicate: if the same field resolves from default across multiple calls within one run, the warning appears once.

# Refinement Iteration 3
**Status:** OPENED

## 1. Executive Summary
This iteration supersedes CFG-001 and CFG-002 from Iteration 2 with a factory-based construction model (Model B). Instead of building a sparse, nullable AppConfig and later running a separate resolver, the `AppConfig` constructor accepts a sparse input dict (e.g., `vars(parsed_args)` from argparse, or an equivalent dict from the webapp) and performs all three-tier resolution internally at construction time. The resulting `AppConfig` object is fully resolved: fields with hardcoded defaults are always typed and non-None; only fields with no hardcoded default anywhere in the chain remain `None`. This eliminates None-guard pollution at every call site and makes `None` on a resolved config unambiguously mean "no value available in any tier."

## 2. Revised Requirements & Acceptance Criteria

- **Requirement CFG-001:** Deterministic Three-Tier Resolution Inside AppConfig Construction
    - **Description:** `AppConfig` MUST be constructed via a factory method (e.g., `AppConfig.from_args(overrides: dict[str, Any])`) that resolves all fields internally in tier order: (1) key present in `overrides` dict, (2) key present in `data/config/settings.json`, (3) hardcoded default. The caller passes only the keys it explicitly has; absent keys are not included in the dict. After construction, the object is fully resolved — no separate resolution step is needed.
    - **Acceptance Criteria:**
        - [ ] Given a key is present in the `overrides` dict, When `AppConfig` is constructed, Then the field takes that value regardless of settings or hardcoded defaults.
        - [ ] Given a key is absent from `overrides` but present in settings, When `AppConfig` is constructed, Then the field takes the settings value.
        - [ ] Given a key is absent from both `overrides` and settings but has a hardcoded default, When `AppConfig` is constructed, Then the field takes the hardcoded default and a per-field warning is emitted.
        - [ ] Given a key is absent from `overrides`, settings, and has no hardcoded default, When `AppConfig` is constructed, Then the field is `None` on the resolved object with no warning emitted.
        - [ ] Given `AppConfig` is constructed, When any caller accesses a field with a hardcoded default, Then the field is always typed non-None without any None-guard required.

- **Requirement CFG-002:** Sparse Dict as the CLI Input Contract
    - **Description:** Each CLI project MUST pass only the arguments it explicitly parsed to `AppConfig.from_args()`, using `vars(parsed_args)` or an equivalent sparse dict. Keys for unprovided optional arguments MUST be absent from the dict (not set to `None`). The webapp and other non-CLI entrypoints pass an empty dict or a dict containing only their known overrides.
    - **Acceptance Criteria:**
        - [ ] Given an optional CLI argument is omitted, When the CLI calls `AppConfig.from_args()`, Then the corresponding key is absent from the input dict (not present as `None`).
        - [ ] Given a required CLI argument is missing, When argument parsing runs, Then the CLI returns a user-facing error before `AppConfig.from_args()` is called.
        - [ ] Given the webapp entrypoint starts with no CLI args, When it constructs config, Then it calls `AppConfig.from_args({})` or with only its known overrides, and resolution falls through to settings and defaults normally.

- **Requirement CFG-003 through CFG-007:** Unchanged from Iteration 2.
    - Project-owned post-resolution validation (CFG-003), all runtime/global options resolved consistently (CFG-004), per-field warnings on hardcoded default fallback (CFG-005), best-effort field-level settings loading (CFG-006), and config-dump diagnostics traceability (CFG-007) remain exactly as specified in Iteration 2.

## 3. Scope & Constraints
- **In-Scope:** Everything from Iteration 2, plus:
    - Replace the two-step "construct nullable AppConfig then resolve" pattern with a single `AppConfig.from_args(overrides)` factory that resolves at construction time.
    - Ensure argparse-generated `Namespace` objects are passed via `vars()` so absent optional args are simply missing keys, not `None` values.
    - The `overrides` dict is the canonical sparse input for all entrypoints (CLI, webapp, tests).
- **Out-of-Scope:** Same as Iteration 2. No changes to storage format, schema validation, or unrelated processing logic.
- **Technical Constraints / Edge Cases:**
    - `argparse` sets absent optional args to `None` by default; CLI code MUST strip `None` values from `vars(parsed_args)` before passing to `from_args()` (e.g., `{k: v for k, v in vars(args).items() if v is not None}`), or use `default=argparse.SUPPRESS` to omit them entirely.
    - The distinction between "key absent" (not provided) and "key present with value" (explicitly provided) is the boundary between tiers 1 and 2. This must be enforced at the dict boundary, not inside AppConfig.
    - All other constraints from Iteration 2 apply unchanged.

## User Additions

The sparse dict that will be passed to `AppConfig.from_args()` must be normalized to the expected entries from `AppConfig`. For example, `md_gen` will need the following maps (these are some examples; must apply to other option domains):
- `language-model-endpoint` -> `{ "language_model": { "endpoint": value } }`
- `ocr-model-endpoint` -> `{ "ocr_model": { "endpoint": value } }`
- `summary-prompt` -> `{ "md_gen": { "summary": { "prompt_path": value } } }`

The same mapping pattern applies for project-specific domains in `md_mrg` or any other project with specific setting sections.

---

# Refinement Iteration 4
**Status:** LOCKED

## 1. Executive Summary
This iteration finalizes all outstanding requirements by formalizing the dict normalization strategy and confirming that all design questions have been answered. Iteration 3's factory-based model combined with the sparse dict normalization pattern provides a complete, unambiguous specification for implementing the three-tier configuration resolution system across all CLI and non-CLI entrypoints.

## 2. Refined Requirements & Acceptance Criteria

- **Requirement CFG-001 through CFG-007:** Unchanged from Iteration 3.
    - All requirements from Iteration 3 (factory-based construction, sparse dict input, project-owned validation, runtime options, warnings, settings loading, and diagnostics traceability) remain unchanged and fully specified.

- **Requirement CFG-008:** CLI Argument to Config Dict Normalization
    - **Description:** When a CLI project constructs the sparse `overrides` dict to pass to `AppConfig.from_args()`, it MUST normalize flat CLI argument names (e.g., `language-model-endpoint`, `ocr-model-endpoint`) into the nested structure expected by AppConfig. This normalization MUST respect the AppConfig schema and match the structure used in `data/config/settings.json` for consistency.
    - **Acceptance Criteria:**
        - [ ] Given a CLI project parses a flat argument like `language-model-endpoint`, When building the `overrides` dict, Then it normalizes to `{ "language_model": { "endpoint": value } }` before passing to `AppConfig.from_args()`.
        - [ ] Given a CLI project parses a project-specific argument like `summary-prompt` for `md_gen`, When building the `overrides` dict, Then it normalizes to `{ "md_gen": { "summary": { "prompt_path": value } } }` matching the settings structure.
        - [ ] Given multiple projects (`md_gen`, `md_mrg`, etc.) have project-specific domains, When each CLI builds its `overrides` dict, Then the normalization pattern is consistent across all projects.
        - [ ] Given the `overrides` dict is normalized to match settings structure, When `AppConfig.from_args()` receives it, Then settings file values can be merged seamlessly without structural mismatch.

## 3. Scope & Constraints
- **In-Scope:**
    - All requirements from Iterations 2-3 regarding three-tier resolution, factory-based construction, project-owned validation, and diagnostics.
    - CLI argument normalization pattern for flat names to nested config structures.
    - Consistency of normalization across all CLI projects and domains.
- **Out-of-Scope:**
    - Refactoring or changing the structure of `data/config/settings.json`.
    - Replacing argparse or changing CLI argument parsing infrastructure.
    - Building new UI flows or non-functional aspects.
- **Technical Constraints / Edge Cases:**
    - The normalization MUST be deterministic: the same CLI argument always maps to the same nested structure.
    - Normalization logic SHOULD be centralized (e.g., in a shared utility function) to prevent duplication across CLI projects.
    - Nested structure in the `overrides` dict must match the nested structure in `settings.json` to ensure seamless merging at tier 2.

**LOCKED**

