# Implementation Analysis: config-module-fix

## 1. Architectural Impact & Data Flow
*High-level overview of how data flows through the system for this feature. Identify any new patterns or structural additions.*
- **Affected Subsystems:** Common configuration loading (`src/common/config.py`), md_gen CLI/runtime config consumption, md_mrg CLI/runtime config consumption, config dump output, configuration tests.
- **Data Flow Changes:** CLI args are parsed per module -> settings.json is loaded as the required baseline -> non-`None` CLI values overlay only allowed scopes (global + invoking module) -> resulting in-memory `AppConfig` mirrors JSON hierarchy (global + `md_gen` + `md_mrg`) without synthetic duplication -> downstream modules read only the fields they need from their scoped sections plus global models.
- **Architectural Pattern Shift:** Move from mixed, module-specific builder behavior in shared config code to a schema-aligned, scope-aware composition model. Shared config code remains generic and hierarchy-preserving; module code is responsible for selecting required fields from `AppConfig`.

## 2. Component & File Impact Map
*Identify the exact files that must be created, modified, or deleted, and what structural changes they require.*

### `./src/common/config.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Align configuration dataclass hierarchy to mirror JSON shape, including explicit module sections for `md_gen` and `md_mrg` under `AppConfig`.
  - [ ] Keep `ocr_model` and `language_model` as global fields; remove shared-loader behavior that synthesizes copies into module-local structures.
  - [ ] Normalize builder/helper signatures so they consume explicit scope inputs and apply the same merge contract everywhere.
  - [ ] Enforce strict required-field validation for required JSON keys (fail-fast with explicit validation errors).
- **Logic Modifications Required:**
  - [ ] Apply deterministic precedence uniformly: JSON first, then non-`None` CLI overrides.
  - [ ] Restrict override scope so md_gen invocation cannot override md_mrg fields and vice versa.
  - [ ] Eliminate mixed-source merges that currently produce conflicting/duplicated model settings.
  - [ ] Extend consistency checks across all config builders/helpers, not only the two examples cited.

### `./src/common/config_dump.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update dump rendering to follow the new `AppConfig` hierarchy (module sections and global sections as distinct scopes).
- **Logic Modifications Required:**
  - [ ] Ensure output reflects scoped values from their real location in `AppConfig` and does not imply synthetic duplication.

### `./src/md_gen/cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Keep argument surface but align handoff to shared config loader with scoped override semantics for global + `md_gen` only.
- **Logic Modifications Required:**
  - [ ] Ensure md_gen CLI overrides only affect global model fields and `md_gen` fields, never `md_mrg`.

### `./src/md_gen/page_processor.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update config field access paths to read image/runtime settings from the new schema-aligned `AppConfig` structure.
- **Logic Modifications Required:**
  - [ ] Preserve current processing behavior while sourcing values from correct scope.

### `./src/md_gen/summarize.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update access to prompt settings and model settings according to revised `AppConfig` hierarchy.
- **Logic Modifications Required:**
  - [ ] Preserve summary behavior while reading prompt/model data from correct global/module sections.

### `./src/md_gen/ocr_processor.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Ensure OCR model lookup uses the global model location in `AppConfig` under the schema-aligned hierarchy.
- **Logic Modifications Required:**
  - [ ] Preserve OCR execution behavior with corrected config pathing.

### `./src/md_mrg/cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Align md_mrg config assembly path with the shared schema-preserving model (rather than ad-hoc composition that can duplicate language settings).
- **Logic Modifications Required:**
  - [ ] Ensure CLI overrides apply only to global + `md_mrg` scopes and do not introduce duplicate language model sources.

  **User: add option to dump the configuration, same way as in `md_gen`.**

### `./src/md_mrg/planner.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update config access expectations if md_mrg settings are nested under a schema-aligned root config object.
- **Logic Modifications Required:**
  - [ ] Preserve planner behavior while sourcing language model and score prompt from correct scopes.

### `./test/common/test_config.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update fixture JSON payloads and assertions to validate schema-shaped `AppConfig` hierarchy.
  - [ ] Add coverage for strict required-field failures on missing required JSON keys.
- **Logic Modifications Required:**
  - [ ] Add matrix coverage for precedence (`None` preserves JSON, non-`None` overrides JSON).
  - [ ] Add scope-isolation coverage proving md_gen args do not mutate md_mrg values and vice versa.
  - [ ] Add regression checks preventing synthetic duplication of global model settings into module scopes.

### `./test/common/test_config_dump.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update expected dump structure/sections to match new hierarchy and field paths.
- **Logic Modifications Required:**
  - [ ] Validate rendered output shows scoped values in the correct sections.

### `./test/md_mrg/test_mrg_plan.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Adjust any config fixtures/mocks if md_mrg consumers receive revised config structure.
- **Logic Modifications Required:**
  - [ ] Preserve planner dispatch assertions while validating compatibility with updated config contracts.

### `./test/md_gen/test_cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update CLI/config integration expectations if config object shape changes in md_gen path.
- **Logic Modifications Required:**
  - [ ] Preserve current CLI behavior assertions while validating scoped override behavior.

## 3. Boundary & Edge Case Analysis
*Detail how system boundaries, errors, and edge cases will be handled structurally.*
- **Error Handling:**
  - Missing required JSON fields must trigger deterministic validation errors (no silent fallbacks for required keys).
  - Invalid prompt file paths or unreadable files remain explicit config validation failures.
  - Scope violations (attempted cross-module override effects) must be structurally prevented by builder boundaries.
- **Security & Permissions:**
  - No new auth/RBAC surfaces.
  - File-system read/write permissions remain relevant for settings and prompt files; failures should continue surfacing through validation errors.
- **Performance / Scale Impact:**
  - Negligible runtime impact; changes are in startup/config assembly.
  - Slight increase in validation checks at startup is acceptable and bounded.
- **Boundary Rules to Preserve:**
  - Explicit duplicate key names across global/module scopes in JSON are valid and must remain separate scoped values.
  - CLI overrides are field-level and scope-limited; no broad cross-section replacement.
  - Strict JSON requirements apply unless a field is explicitly optional in schema.

## 4. Verification Checklist
*A concrete list of what needs to be verified during/after implementation to ensure the analysis was correct.*
- [ ] Verify `AppConfig` produced by shared loader mirrors settings.json hierarchy (global + `md_gen` + `md_mrg`) without synthetic reshaping.
- [ ] Verify global `ocr_model` and `language_model` remain single global sources unless JSON explicitly duplicates model-related keys in module sections.
- [ ] Verify every builder/helper in `src/common/config.py` follows the same precedence contract (JSON base, non-`None` CLI overlay).
- [ ] Verify md_gen CLI overrides affect only global and `md_gen` fields.
- [ ] Verify md_mrg CLI overrides affect only global and `md_mrg` fields.
- [ ] Verify same-name fields in non-invoked module sections are unchanged after CLI overlay.
- [ ] Verify missing required JSON keys fail with explicit validation errors.
- [ ] Verify optional/defaulted fields (if explicitly defined as optional) retain documented default behavior without weakening strict required-key validation.
- [ ] Verify md_gen runtime still processes files correctly using updated config access paths.
- [ ] Verify md_mrg planner/apply flows still run correctly using updated config access paths.
- [ ] Verify verbose config dump reflects corrected hierarchy and scoped values.
- [ ] Verify updated tests cover precedence, scope isolation, strict validation, and no-duplication regressions.
---
