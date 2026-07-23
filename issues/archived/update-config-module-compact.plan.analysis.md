# Implementation Analysis: update-config-module-compact

## 1. Architectural Impact & Data Flow
*High-level overview of how data flows through the system for this feature. Identify any new patterns or structural additions.*
- **Affected Subsystems:** Shared configuration loading in `src/common/config.py`, plain config rendering in `src/common/config_dump.py`, CLI entrypoints in `src/md_gen/cli.py`, `src/md_mrg/cli.py`, and `src/llm_cli/cli.py`, runtime consumers that read `AppConfig`, webapp settings loading in `src/webapp/backend/settings_store.py` and `src/webapp/backend/app.py`, and configuration-focused tests.
- **Data Flow Changes:** Entry point arguments or non-CLI inputs are normalized into sparse nested override payloads -> shared config resolution loads `data/config/settings.json` on a best-effort basis -> recognized settings fields merge with overrides and hardcoded defaults using one deterministic per-field precedence chain -> unresolved optional fields may remain `None` -> each consuming project performs its own required-input and filesystem validation after resolution and before starting work.
- **Architectural Pattern Shift:** Separate shared responsibilities from project responsibilities. Shared config code becomes a field-oriented resolver and default-warning layer rather than a runtime gatekeeper. CLI and non-CLI consumers become responsible for building scoped override payloads and for enforcing their own execution preconditions.

## 2. Component & File Impact Map
*Identify the exact files that must be created, modified, or deleted, and what structural changes they require.*

### `./src/common/config.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Rework the shared configuration surface around a schema-aligned, nested override input contract instead of `SimpleNamespace`-specific field probing.
  - [ ] Make nullable fields explicit in the shared config model for values that may remain unresolved after all three tiers are exhausted.
  - [ ] Isolate project-agnostic helpers for settings-file loading, nested-field extraction, per-field coercion, and default application from project-specific builders such as path validation and prompt-file loading.
  - [ ] Preserve a single `AppConfig` root that still matches the settings hierarchy (`ocr_model`, `language_model`, `md_gen`, `md_mrg`, `runtime` or equivalent global scope) so CLI and webapp inputs merge into the same structure.
- **Logic Modifications Required:**
  - [ ] Apply the same precedence chain to every shared field: override first, then settings, then hardcoded default, with unresolved optional fields left as `None`.
  - [ ] Treat `None` as missing during resolution so sparse overrides do not block settings or defaults.
  - [ ] Stop raising shared configuration errors for project-owned required inputs such as source/output paths and project prompt requirements; move those checks behind project validation boundaries.
  - [ ] Load settings in a best-effort, field-oriented manner so unknown keys are ignored, invalid recognized values are skipped as missing, and file bootstrap/read failures degrade to an empty settings view instead of aborting resolution.
  - [ ] Emit one warning per field that resolves from a hardcoded default, and suppress warnings for fields satisfied by overrides or settings.

### `./src/common/config_dump.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Keep the dump renderer focused on presenting resolved config values in the existing hierarchy.
  - [ ] Ensure the dump output remains readable when a field is unresolved and prints the actual value shape rather than an inferred provenance label.
- **Logic Modifications Required:**
  - [ ] Keep config-dump output aligned with the nested config hierarchy that resolution uses.
  - [ ] Preserve the existing startup dump behavior so verbose/debug output shows what values will be used without duplicating the default-warning diagnostics emitted during resolution.

### `./src/md_gen/cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace direct `SimpleNamespace` pass-through with explicit construction of a sparse, nested override payload for `md_gen`, shared global model settings, and runtime flags.
  - [ ] Add or preserve a project validation stage after config resolution and before bootstrap begins.
- **Logic Modifications Required:**
  - [ ] Ensure omitted optional flags are absent from overrides rather than prefilled.
  - [ ] Keep argparse responsible for required command-line arguments and user-facing parse failures.
  - [ ] Move md_gen-specific required path and prompt precondition failures to md_gen-owned validation logic rather than shared resolution.

### `./src/md_mrg/cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace direct shared-builder invocation with explicit sparse override normalization for `md_mrg`, global language-model settings, and runtime flags.
  - [ ] Add or preserve a project validation stage for md_mrg-owned prerequisites before planner/apply execution.
- **Logic Modifications Required:**
  - [ ] Normalize flat CLI names into the nested settings shape expected by shared resolution.
  - [ ] Ensure md_mrg consumes the same runtime/global precedence rules as md_gen and webapp entrypoints.
  - [ ] Report missing or invalid source/output requirements from md_mrg-owned validation, not from shared config assembly.

### `./src/llm_cli/cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Convert flat CLI arguments into a sparse override payload compatible with the shared nested resolver.
  - [ ] Clarify which values are resolved through shared config versus which prompt-file arguments remain direct CLI concerns.
- **Logic Modifications Required:**
  - [ ] Stop relying on the shared builder to infer unrelated path/project requirements for a chat-only entrypoint.
  - [ ] Keep post-resolution mutation of language-model sampling fields aligned with the new runtime/global resolution contract or fold those fields into the same shared override path.

### `./src/md_gen/foundation.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Introduce or consume an md_gen-specific validation boundary that runs after config resolution and before file discovery/processing.
- **Logic Modifications Required:**
  - [ ] Enforce required source/output accessibility checks at the md_gen runtime boundary instead of inside shared config resolution.

### `./src/md_mrg/planner.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Accept config values that may now be nullable until md_mrg validation confirms required inputs are present.
- **Logic Modifications Required:**
  - [ ] Preserve planner behavior while relying on md_mrg-owned validation to guarantee required fields are available before planning starts.

### `./src/md_mrg/apply.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Align apply-time assumptions with the same post-resolution validation boundary used for planner execution.
- **Logic Modifications Required:**
  - [ ] Preserve apply behavior while reading resolved config from the same shared precedence model.

### `./src/webapp/backend/settings_store.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Decide whether the webapp remains the owner of persistence/atomic writes while delegating read-time resolution of runtime/global defaults to the shared config module, or whether it must add an adapter layer from `AppSettings` to shared config resolution.
  - [ ] Keep webapp storage concerns separate from shared resolution concerns so API persistence does not inherit CLI-only validation rules.
- **Logic Modifications Required:**
  - [ ] Ensure the webapp startup and workflow endpoints resolve runtime/global options through the same precedence chain as CLI entrypoints.
  - [ ] Avoid a second incompatible interpretation of missing settings fields at the API boundary.

### `./src/webapp/backend/app.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Route workflow startup/processing paths through whichever shared config resolution entrypoint becomes the non-CLI counterpart for the webapp.
- **Logic Modifications Required:**
  - [ ] Make workflow endpoints consume resolved settings and project validation in the same order as CLI flows: resolve shared fields first, then enforce endpoint-specific prerequisites.

### `./src/webapp/backend/models.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Reconcile the Pydantic settings schema with the shared resolver’s optional-field contract where hardcoded defaults or nullable values now exist.
  - [ ] Distinguish persisted document shape from resolved runtime shape if the webapp continues to store a stricter schema than the shared resolver requires.
- **Logic Modifications Required:**
  - [ ] Prevent model validation from reintroducing fail-fast behavior for fields that the shared resolver is supposed to treat as missing and continue past.

### `./test/common/test_config.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace tests that assume `SimpleNamespace`-driven construction or shared fail-fast validation with cases centered on nested sparse overrides and shared field resolution.
- **Logic Modifications Required:**
  - [ ] Add coverage for all three precedence tiers.
  - [ ] Add coverage proving `None` and omitted keys continue the resolution chain.
  - [ ] Add coverage for best-effort settings loading: unknown keys ignored, bad field values skipped, unreadable settings treated as empty.
  - [ ] Add coverage for per-field default warnings.

### `./test/common/test_config_dump.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update fixtures and expected renderings to match the value-only startup dump.
- **Logic Modifications Required:**
  - [ ] Verify verbose/debug dumps continue to render the resolved config values in the expected hierarchy.

### `./test/md_gen/test_cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update CLI integration tests to assert nested override normalization rather than raw argparse namespace forwarding.
- **Logic Modifications Required:**
  - [ ] Verify optional omitted flags do not appear in overrides.
  - [ ] Verify verbose output still runs after shared resolution and before md_gen execution.
  - [ ] Verify md_gen project validation reports explicit runtime errors for missing/unusable paths after config resolution.

### `./test/md_mrg/test_mrg_plan.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update md_mrg CLI fixtures to reflect nested override normalization and shared resolution output.
- **Logic Modifications Required:**
  - [ ] Verify md_mrg verbose startup dump remains available.
  - [ ] Verify md_mrg plan/apply paths fail at project validation boundaries for missing required runtime inputs.

### `./test/llmcli/test_chat.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update llm_cli config fixtures if the resolved runtime/global shape or construction path changes.
- **Logic Modifications Required:**
  - [ ] Verify llm_cli can resolve language-model/global defaults without requiring unrelated filesystem settings.

### `./test/webapp_tests/test_settings_store.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Adjust expectations if persisted settings shape and resolved runtime shape become distinct concepts.
- **Logic Modifications Required:**
  - [ ] Verify webapp persistence remains atomic while compatible with the shared precedence contract.

### `./test/webapp_tests/test_settings_api.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update API expectations if settings reads now expose optional/missing-field behavior separately from persisted document validation.
- **Logic Modifications Required:**
  - [ ] Verify saved settings are still round-tripped correctly and that runtime/global defaults are interpreted consistently downstream.

### `./test/webapp_tests/test_workflow_api.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update workflow-start fixtures so the backend resolves config through the new shared path before workflow execution.
- **Logic Modifications Required:**
  - [ ] Verify workflow endpoints apply the same precedence rules as CLI entrypoints for runtime/global values.

## 3. Boundary & Edge Case Analysis
*Detail how system boundaries, errors, and edge cases will be handled structurally.*
- **Error Handling:** Shared configuration loading should stop reporting project-specific missing-input errors and instead produce a resolved config that may contain `None` for unresolved optional/shared fields. Each consumer must then raise its own explicit runtime or startup errors for required paths, unreadable prompt files, missing folders, or unwritable outputs before work begins. Settings-file absence, unreadable settings, or malformed recognized fields should degrade to missing-field behavior rather than aborting the entire startup path.
- **Security & Permissions:** No new auth or permission model is introduced. Filesystem access remains the main boundary: shared resolution may read the settings file, while project validators remain responsible for checking directory existence, creating outputs where appropriate, and surfacing permission failures with project-relevant error messages.
- **Performance / Scale Impact:** Impact remains limited to startup and request initialization. Best-effort settings parsing should avoid repeated full-document reparsing across consumers where possible, especially for webapp endpoints that currently load settings repeatedly.
- **Boundary Rules to Preserve:**
  - [ ] The nested override shape must align with the persisted settings hierarchy so merge behavior is deterministic.
  - [ ] Unknown settings keys remain ignored rather than rejected.
  - [ ] `None` and missing keys are distinct from explicit scalar overrides and must not short-circuit fallback resolution.
  - [ ] Fields without hardcoded defaults may remain unresolved after shared resolution.
  - [ ] Default warnings must be emitted once per field, not once per section.
  - [ ] Webapp persistence concerns must remain separated from shared runtime resolution so API storage rules do not become CLI validation rules.

## 4. Verification Checklist
*A concrete list of what needs to be verified during/after implementation to ensure the analysis was correct.*
- [ ] Verify every shared field resolves in the order override -> settings -> hardcoded default.
- [ ] Verify fields without hardcoded defaults remain `None` when absent from overrides and settings.
- [ ] Verify sparse CLI override payloads omit optional values that were not provided.
- [ ] Verify flat CLI names normalize into nested override structures that match the settings document shape.
- [ ] Verify shared config resolution no longer fails because a consuming project does not need a particular path or prompt field.
- [ ] Verify md_gen reports explicit post-resolution errors for missing or unusable source/output inputs before processing starts.
- [ ] Verify md_mrg reports explicit post-resolution errors for missing or unusable runtime inputs before planning or apply starts.
- [ ] Verify llm_cli can resolve only the global fields it owns without inheriting unrelated path requirements.
- [ ] Verify webapp runtime/global options use the same precedence chain as CLI entrypoints.
- [ ] Verify unknown settings keys are ignored and invalid recognized fields are skipped without aborting the full load.
- [ ] Verify unreadable or missing settings files degrade to an empty settings view rather than terminating shared resolution.
- [ ] Verify one warning is emitted for each field that falls back to a hardcoded default.
- [ ] Verify no default warning is emitted for fields resolved from overrides or settings.
- [ ] Verify verbose or debug config-dump output continues to show the resolved configuration values in the expected hierarchy.
- [ ] Verify persisted settings behavior in the webapp remains compatible with the shared resolver without reintroducing strict fail-fast behavior for optional runtime fields.
---