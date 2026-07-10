# Issue 5 - Keep Only LLM for Bridge Score (Implementation Analysis)

## 1. Objective and Scope

This issue simplifies both `md_gen` and `md_mrg` contracts to reduce configuration complexity, remove unused/low-value paths, and make behavior deterministic for local workflows.

Primary outcomes:
- Enforce simplified directory contracts with required named flags.
- Standardize intermediate artifacts under one folder: `output/temp`.
- Externalize LLM prompts to files with safe defaults and optional overrides.
- Keep scoring interface abstraction but remove heuristic scoring implementation.
- Keep `edge-scorer` argument constrained to `llm` only.
- Reorganize tests per module and introduce coverage requirements per module.
- Remove backward-compatibility code and obsolete CLI arguments now.

Out of scope for this issue:
- Backend/frontend integration.
- New OCR/model capabilities.
- Functional redesign of planner/apply into a single command.

## 2. Current State vs Target State

### 2.1 Current State (Problem)

- CLI behavior allows multiple source forms and optional output/temp routing, creating ambiguity.
- Temp locations are configurable via multiple arguments, which increases path and test complexity.
- Bridge scoring includes heuristic and LLM options, but heuristic quality is not meeting desired results.
- Prompt text behavior is not fully file-driven for easy prompt experimentation.
- Tests are mixed at top-level `test` and not clearly separated by module responsibility.

### 2.2 Target State (Required)

- `md_gen` uses explicit required flags: `--source` and `--output`.
- `md_mrg` uses explicit required flag: `--source`.
- Discovery and processing become deterministic under fixed path conventions.
- Prompt sourcing is standardized with default in-repo files plus override flags.
- LLM is the only bridge-scoring behavior.
- Planner/apply remain two separate workflows with deterministic plan-file naming.
- Observability moves to console output (including consumed/skipped discovery decisions).

## 3. Contract Changes Required

## 3.1 MD_GEN Contract Requirements

- Input contract:
  - Accept only directory path in `--source`.
  - Reject file-path source inputs.
  - Require `--output` and create output directory if missing.
- Discovery contract:
  - Non-recursive scan only.
  - Supported image extensions: `.png`, `.jpg`, `.jpge`.
  - PDF support remains enabled.
  - Unsupported files are skipped.
  - Console must print discovered files and consumed/skipped decision.
- Path contract:
  - Intermediate artifacts live in `output/temp`.
  - Existing `output/temp` content is preserved (no automatic cleanup).
  - Remove `md-temp-dir` and `mg-temp-dir` arguments/paths.
- Prompt contract:
  - Summary prompt loaded from default in-repo file.
  - Optional override with `--summary-prompt`.
  - If file read fails, fallback to built-in prompt text.
  - Prompt format is plain text mapped to `system_prompt`.

## 3.2 MD_MRG Contract Requirements

- Input contract:
  - Use only `--source` required named flag.
  - `--source` is expected to point to MD_GEN output root.
- Planner/apply contract:
  - Keep planner and apply as separate command paths.
  - Planner reads from `source/temp` and writes deterministic JSON batch in `source`.
  - Apply reads plan JSON from `source`.
- Scorer contract:
  - Keep scorer interface abstraction for maintainability.
  - Remove heuristic implementation and all selection paths.
  - Keep `edge-scorer` argument but constrain it to `llm` only.
- Prompt contract:
  - Score prompt loaded from default in-repo file.
  - Optional override with `--score-prompt`.
  - Missing/unreadable file falls back to built-in default text.

## 3.3 Error and Logging Contract Requirements

- Error outputs must include:
  - machine-readable error code
  - human-readable message
- Console output is the authoritative runtime output channel.
- File logging behavior is removed from scope.

## 4. Architecture Impact by Module

## 4.1 `src/md_gen`

Impact areas:
- CLI parsing and validation for strict `--source`/`--output` contract.
- Discovery logic to enforce single-level scanning and explicit extension filtering.
- Path resolution to eliminate configurable temp dirs and force `output/temp` layout.
- Prompt loading utility/path handling for summary prompt default + override + fallback.
- Console reporting for discovery inclusion/exclusion decisions.
- Error model update to include machine code + readable text.

## 4.2 `src/md_mrg`

Impact areas:
- CLI parsing changes for the same strict flag contract and removal of temp-dir args.
- Planner/apply path derivation aligned to `source/temp` input and `source` plan files.
- Scorer module cleanup:
  - keep interface
  - delete heuristic scorer implementation and selection branch
  - enforce llm-only option semantics
- Prompt loading for scoring prompt default + override + fallback.
- Deterministic JSON naming policy enforcement for planner output.

## 4.3 `src/common`

Potential cross-cutting impact:
- Shared prompt loading and error formatting utilities may be needed to avoid duplicated behavior between modules.
- If common logging helpers exist, they need reconciliation with console-only output requirement.
- Use always the common/llama_gateway.py, to avoid code clutter we will remove md_gen/gateway.py which is just kind of an alias.

## 5. Data and Artifact Impact

- Intermediate artifact location is canonicalized:
  - `output/temp` for md/json/image temporary artifacts.
- Planning artifact location is canonicalized:
  - deterministic plan JSON files in `source`.
- Existing user workflows that depended on custom temp paths are intentionally invalidated.

## 6. Test and Quality Impact

Required test-structure changes:
- Move MD_GEN tests under `test/md_gen`.
- Move MD_MRG tests under `test/md_mrg`.
- Move first, then fix to preserve history and reduce simultaneous refactor risk.

Required test coverage focus:
- CLI validation for required flags and folder-only constraints.
- Discovery filtering and consumed/skipped console reporting.
- Prompt file loading: default path, override path, fallback behavior.
- Path normalization and temp location invariants.
- LLM-only scorer enforcement (`edge-scorer=llm` only).
- Planner/apply I/O path contracts and deterministic plan filename behavior.
- Error code + message formatting.

Coverage policy impact:
- Add coverage tooling configuration to `pyproject.toml`.
- Enforce initial minimum coverage threshold of 60%.
- Coverage reporting split per module (`md_gen`, `md_mrg`).

## 7. Breaking Changes and Migration Notes

Intentional breaking changes:
- Removal of `md-temp-dir` and `mg-temp-dir` arguments.
- Removal of heuristic scorer behavior.
- Removal of backward-compatibility shims.

Documentation impact:
- README/CLI help text must be aligned with new flag contracts and path behavior.
- Any examples using old args should be removed.

## 8. Risks and Constraints

Key risks:
- Tightening CLI/path contracts may break existing local scripts immediately.
- Removing heuristic scorer eliminates fallback if LLM endpoint is unavailable.
- Prompt-file fallback behavior can mask missing file errors if not clearly surfaced in console output.
- Console-only output may reduce post-run traceability unless messages are sufficiently structured.

Constraints from decisions:
- No deprecation period.
- No log-file requirement.
- Keep planner and apply split.

## 9. Validation Criteria for Analysis Completion

This analysis is complete when all of the following are recognized as required by implementation planning:
- Strict CLI contracts with `md_gen` using `--source`/`--output` and `md_mrg` using `--source` only.
- Unified path contract centered on `<root>/temp` (`output/temp` in `md_gen`, `source/temp` in `md_mrg`).
- Prompt file defaults/overrides/fallbacks for both summary and scoring.
- LLM-only bridge scoring with interface retained.
- Deterministic planner output in `source` with apply reading same location.
- Structured error output and console-only runtime reporting.
- Test migration + fixes + module-scoped coverage policy (60% minimum).

## 10. Items to Confirm Before Writing the Implementation Plan

- Extension list includes `.jpge` exactly as specified; confirm whether this is intentional or should be `.jpeg`.
- Exact deterministic naming rule for planner JSON (fixed filename vs deterministic stem rule).
- Exact default in-repo prompt file paths for summary and score prompts.
- Required machine error code taxonomy (prefix/naming conventions) to keep consistency across modules.
