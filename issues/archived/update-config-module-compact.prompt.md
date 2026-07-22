# Implementation Plan: update-config-module-compact

> **Core Objective:** Detailed step-by-step technical execution blueprint for implementing the requirements specified in the analysis.

## Traceability

- **Analysis Reference:** [update-config-module-compact.plan.analysis.md](./update-config-module-compact.plan.analysis.md)
- **Issue Name:** `update-config-module-compact`
- **Scope Guard:** Implement only the configuration-resolution refactor, the related CLI/webapp adapters, and the focused tests described in the analysis. Do not change unrelated OCR, merge, frontend, or docs behavior.

## Phase 1: Shared Config Resolution and Settings Loading

Implementing requirements from Analysis Section 2 `src/common/config.py`, Analysis Section 3 Boundary & Edge Case Analysis, and CFG-001, CFG-003, CFG-005, CFG-006, and CFG-007.

### Steps

1. Rework `src/common/config.py` around a sparse nested override contract instead of `SimpleNamespace` probing. Add a small internal resolver that reads fields in strict tier order: override value, then `data/config/settings.json`, then hardcoded default. Treat `None` and missing keys as equivalent missing input so resolution keeps falling through. This implements CFG-001 and CFG-008.
2. Make the shared config model explicit about nullable values where no hardcoded default exists. Keep the top-level `AppConfig` hierarchy intact, but stop forcing project-owned required inputs such as source/output paths or prompt files inside the shared module. Those checks move to the consuming project boundaries. This implements CFG-003.
3. Replace fail-fast settings-file handling with best-effort field loading. Unknown keys must be ignored, invalid recognized values must be skipped as missing, and unreadable or absent settings must behave like an empty settings document. Emit one warning for each field that resolves from a hardcoded default and no warning for values resolved from overrides or settings. This implements CFG-005, CFG-006, and CFG-007.

### Exit Criterion

`src/common/config.py` can resolve a complete `AppConfig` from sparse nested overrides and an optional settings file without aborting on missing project-specific inputs, while default-backed fields emit one warning each.

### Validation Command

```powershell
uv run pytest test/common/test_config.py test/common/test_config_dump.py
```

## Phase 2: CLI Override Normalization and Post-Resolution Validation

Implementing requirements from Analysis Section 2 `src/md_gen/cli.py`, `src/md_mrg/cli.py`, `src/llm_cli/cli.py`, `src/md_gen/foundation.py`, `src/md_mrg/planner.py`, and `src/md_mrg/apply.py`, plus CFG-002, CFG-003, and CFG-008.

### Steps

1. Replace direct `SimpleNamespace` pass-through in `src/md_gen/cli.py`, `src/md_mrg/cli.py`, and `src/llm_cli/cli.py` with explicit sparse override builders. Normalize flat CLI names into nested dictionaries that match the settings hierarchy, and omit optional values that were not provided. Keep argparse responsible only for required-argument failures. This implements CFG-002 and CFG-008.
2. Move project-owned validation to the runtime boundaries that actually need it. `md_gen` should validate source/output/prompt prerequisites after shared resolution and before bootstrap work starts; `md_mrg` should validate its source and merge prerequisites before planning/apply execution; `llm_cli` should only validate the prompt and model inputs it owns. Do not let shared config assembly raise these errors. This implements CFG-003.
3. Keep any post-resolution mutation of sampling or runtime fields aligned with the same shared resolution contract. If a CLI option belongs in the shared settings hierarchy, normalize it into the override payload instead of mutating the resolved config in place. This keeps all global and runtime options on the same path required by CFG-004.

### Exit Criterion

Each CLI entrypoint feeds a sparse nested override payload into shared config resolution, and each project surfaces its own missing-path or unusable-input errors only after resolution.

### Validation Command

```powershell
uv run pytest test/md_gen/test_cli.py test/md_gen/test_foundation.py test/md_mrg/test_mrg_plan.py test/llmcli/test_chat.py
```

## Phase 3: Webapp Settings Bridge and Config Dump Alignment

Implementing requirements from Analysis Section 2 `src/webapp/backend/settings_store.py`, `src/webapp/backend/app.py`, and `src/webapp/backend/models.py`, plus CFG-004, CFG-006, and CFG-007.

### Steps

1. Keep `src/webapp/backend/settings_store.py` focused on persistence and atomic writes, but add an adapter that can feed persisted settings into the shared resolver without reusing CLI-only validation rules. The stored document remains the source of truth on disk; the shared resolver is only responsible for producing the runtime view. This implements CFG-004 and CFG-006.
2. Update `src/webapp/backend/app.py` so workflow and settings endpoints load persisted settings first, resolve shared runtime/global values through the same precedence chain as the CLI, and then apply endpoint-specific validation. Any missing field behavior should be resolved by the shared module, not reinterpreted in the route handlers. This implements CFG-004 and CFG-003.
3. Keep `src/common/config_dump.py` value-only and aligned with the nested hierarchy used by resolution. The dump should show resolved values in the existing startup layout without adding provenance noise or duplicating default warnings. This implements CFG-007.

### Exit Criterion

The webapp can load persisted settings, resolve runtime/global defaults through the shared chain, and continue to use atomic storage without turning persistence into a second validation system.

### Validation Command

```powershell
uv run pytest test/webapp_tests/test_settings_store.py test/webapp_tests/test_settings_api.py test/webapp_tests/test_workflow_api.py
```

## Phase 4: Final Regression Verification

Implementing requirements from Analysis Section 4 Verification Checklist and CFG-001 through CFG-008.

### Steps

1. Run the focused common, CLI, and webapp tests together to confirm the full configuration flow, default-warning behavior, sparse override normalization, and config dump output stay stable after the refactor. This verifies the acceptance criteria behind CFG-001 through CFG-008.
2. If a regression appears, repair the smallest affected slice and rerun the same targeted tests before widening the scope. Keep the fix inside the owning boundary instead of reintroducing shared fail-fast checks. This preserves the boundary rules from Analysis Section 3.

### Exit Criterion

All targeted tests pass, and the refactored configuration flow satisfies the resolution, validation, warning, and dump behavior described in the analysis.

### Validation Command

```powershell
uv run pytest test/common/test_config.py test/common/test_config_dump.py test/md_gen/test_cli.py test/md_gen/test_foundation.py test/md_mrg/test_mrg_plan.py test/llmcli/test_chat.py test/webapp_tests/test_settings_store.py test/webapp_tests/test_settings_api.py test/webapp_tests/test_workflow_api.py
```