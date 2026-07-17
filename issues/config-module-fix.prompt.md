> **Analysis Reference:** [config-module-fix.plan.analysis.md](./config-module-fix.plan.analysis.md)
> **Traceability Scope:** Analysis Sections 1-4, Requirements CFG-001 through CFG-006
> **Implementation Target:** Shared config loading, config dump rendering, md_gen/md_mrg CLI wiring, downstream config consumers, and tests

# Implementation Plan: config-module-fix
> **Core Objective:** Detailed step-by-step technical execution blueprint for implementing the requirements specified in the analysis.

## Phase 1: Rebuild the shared configuration contract and loader
**Traceability:** Implements Analysis Section 1, Section 2 (`src/common/config.py`), and Section 3; covers CFG-001 through CFG-006.

**Goal:** Make `src/common/config.py` mirror the JSON schema and enforce one merge rule everywhere: load JSON first, then overlay only non-`None` CLI values that belong to the current command scope.

**Steps:**
1. Redesign the config dataclass layer so the in-memory shape mirrors the real settings file and does not synthesize module copies of shared fields. Keep `ocr_model` and `language_model` as top-level global values, and represent module-specific data in dedicated nested sections for `md_gen` and `md_mrg`.
2. Replace the ad hoc builder behavior with a single scope-aware merge pattern that every helper follows: resolve the JSON section required by that helper, then apply only non-`None` overrides from the allowed CLI scope.
3. Tighten validation so required JSON keys fail fast with explicit `ConfigValidationError` codes instead of falling back silently. Preserve the currently documented defaults only for fields that are intentionally optional/defaulted in the schema.
4. Split the current mixed-source `md_mrg` composition so the language model comes from the global config path and the merge-specific prompt stays in the `md_mrg` section; do not duplicate model settings into module-local structures unless the JSON explicitly contains them.
5. Keep the existing path/runtime resolution behavior for `md_gen`, but move its lookups through the new schema-aligned config structure so consumers read the correct section instead of a synthetic flattening.

**Exit Criterion:** `build_config_from_args` and `build_md_mrg_config_from_args` both produce schema-aligned configs from the same precedence rule, missing required JSON keys fail deterministically, and scope isolation is enforced by construction.

**Validation Command:** `uv run pytest test/common/test_config.py -q`

## Phase 2: Rewire the CLI and config dump surfaces
**Traceability:** Implements Analysis Section 2 (`src/common/config_dump.py`, `src/md_gen/cli.py`, `src/md_mrg/cli.py`) and CFG-004; covers the user request to add config dumping to `md_mrg`.

**Goal:** Make both CLIs consume the shared loader consistently and expose the same verbose config dump behavior.

**Steps:**
1. Update `md_gen` CLI handoff so it continues to accept the same arguments, but only passes the global plus `md_gen`-scoped override values into shared config assembly.
2. Add a verbose config dump option to `md_mrg` that mirrors the `md_gen` behavior: parse the flag, build the config, print the formatted dump before dispatching to plan/apply, and keep normal exit handling unchanged.
3. Reformat `format_config_dump` so it renders the new config hierarchy explicitly, with distinct sections for the global model settings and each module scope that actually exists in `AppConfig`.
4. Make sure the dump output shows values from their real storage location in the config object and does not imply that shared values were copied into unrelated module sections.

**Exit Criterion:** Both CLIs expose consistent startup config visibility, and `md_mrg` can emit the same style of dump as `md_gen` without changing plan/apply behavior.

**Validation Command:** `uv run pytest test/common/test_config_dump.py test/md_gen/test_cli.py -q`

## Phase 3: Update downstream consumers to the new config shape
**Traceability:** Implements Analysis Section 2 (`src/md_gen/page_processor.py`, `src/md_gen/summarize.py`, `src/md_gen/ocr_processor.py`, `src/md_mrg/planner.py`) and Section 3 boundary rules; covers CFG-001, CFG-002, and CFG-005.

**Goal:** Keep runtime behavior unchanged while each consumer reads from the correct scope in the revised config object.

**Steps:**
1. Update `md_gen` consumers so they read path, image, prompt, runtime, and model values from the new `AppConfig` structure without expecting loader-side duplication.
2. Keep OCR extraction pointed at the global OCR model values and keep summary generation pointed at the global language model plus the module prompt text.
3. Update merge planning so it reads the global language model and the `md_mrg` score prompt from the schema-aligned config instead of relying on the previous mixed-source assembly.
4. Preserve the existing processing and planning logic; only the config access paths should change.

**Exit Criterion:** `md_gen` and `md_mrg` still execute the same workflows, but every config read comes from the correct scope and no consumer depends on synthetic duplication.

**Validation Command:** `uv run pytest test/md_gen test/md_mrg/test_mrg_plan.py -q`

## Phase 4: Expand and align the regression tests
**Traceability:** Implements Analysis Section 2 (`test/common/test_config.py`, `test/common/test_config_dump.py`, `test/md_gen/test_cli.py`, `test/md_mrg/test_mrg_plan.py`) and Section 4; covers CFG-001 through CFG-006.

**Goal:** Lock in the new behavior with tests that prove hierarchy preservation, scope isolation, required-field validation, and the new md_mrg dump option.

**Steps:**
1. Update config tests to assert the new config hierarchy, the JSON-first/non-`None` override rule, and the scope restriction that md_gen arguments cannot mutate md_mrg values and vice versa.
2. Add regression coverage for strict missing-field failures so the loader fails when required JSON keys are absent.
3. Update dump tests to assert the new section layout and that multiline prompt text is preserved exactly.
4. Extend CLI coverage so `md_gen` still dumps config when verbose and `md_mrg` now does the same.
5. Update planner tests only where config fixtures or constructor expectations change; keep the behavioral assertions on grouping and scoring intact.

**Exit Criterion:** The test suite proves the new config contract end-to-end, including the md_mrg verbose dump path and all scope-isolation rules.

**Validation Command:** `uv run pytest test/common test/md_gen test/md_mrg -q`

## Final Check
**Traceability:** Completes Analysis Section 4 verification checklist.

Before handoff, run the full targeted suite once more and confirm there are no lingering references to the old flattened or duplicated config shape.

**Validation Command:** `uv run pytest -q`
