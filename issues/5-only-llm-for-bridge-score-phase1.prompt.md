# Issue 5 - Phase 1 Implementation Plan (md_gen + Shared Gateway Cleanup)

Analysis file: `issues/5-only-llm-for-bridge-score.plan.analysis.md`

## 1. Phase Goal

Deliver the md_gen-side contract simplification and shared-gateway cleanup required by Issue 5.

This phase establishes the new ingestion contract and artifact layout so Phase 2 can consume a stable source folder contract.

## 2. Scope of This Phase

In scope:
- md_gen CLI contract migration to required `--source` and `--output` flags.
- Remove multi-source and source-list ingestion behavior from md_gen.
- Single-level discovery only, with explicit consumed/skipped console reporting.
- Canonical temp layout under `output/temp` for md_gen intermediate artifacts.
- Prompt externalization for summaries with default file + `--summary-prompt` override + built-in fallback.
- Machine-readable error code + human-readable error text behavior.
- Console-only output model for this phase (no file-log dependency).
- Apply the new `src/common/llama_gateway.py` policy by removing `src/md_gen/gateway.py` alias usage and deleting alias file.
- Move md_gen tests to `test/md_gen`, then fix failures and expand coverage.

Out of scope:
- md_mrg CLI/scorer/planner/apply refactor (Phase 2).
- UI/backend changes.

## 3. Preconditions and Dependencies

- Phase 1 must preserve compatibility with existing `src/common/llama_gateway.py` contracts used by md_gen runtime.
- Prompt default file path must be defined in-repo before wiring CLI overrides.
- The `.jpge` extension requirement is treated as intentional in this phase unless changed by a later decision.

## 4. Design Decisions Locked for This Phase

- md_gen requires both `--source` and `--output`.
- `--source` must be a directory.
- Discovery is non-recursive (top-level entries only).
- Supported discovery set: PDFs + `.png`, `.jpg`, `.jpge`.
- Unsupported files are skipped and printed as skipped.
- Output folder is auto-created if missing.
- Intermediate artifacts are written under `output/temp`.
- Existing `output/temp` content is not auto-cleaned.
- Summary prompt loading order:
  1) `--summary-prompt` if provided and readable
  2) default in-repo prompt file if readable
  3) built-in prompt constant as fallback

## 5. Implementation Workstreams

## 5.1 CLI and Config Contract Refactor

Target files:
- `src/md_gen/cli.py`
- `src/md_gen/config.py`
- `src/md_gen/foundation.py` (if path/contract assumptions are embedded)

Required changes:
- Replace append/list source args with exactly one `--source` argument.
- Remove `--source-list-file` support from parser/config.
- Replace `--output-dir` naming with `--output` contract.
- Remove temp/log path args from md_gen CLI:
  - `--im-temp-dir`
  - `--md-temp-dir`
  - `--log-file`
- Keep runtime/network flags that remain valid for OCR and language model connectivity.
- Update config dataclasses to represent new path model:
  - source root
  - output root
  - derived temp root (`output/temp`)
  - derived image/markdown/metadata subpaths if needed by current pipeline internals

Validation constraints to enforce:
- Missing `--source` or `--output` must fail fast.
- `--source` path that is not an existing directory must fail with coded error.
- `--output` path must be created if absent.

## 5.2 Discovery and Source Filtering Contract

Target files:
- `src/md_gen/discovery.py`
- `src/md_gen/foundation.py` (or orchestrator stage wiring)

Required changes:
- Enforce one-level directory scan only.
- Define explicit allow-list behavior for image extensions plus PDFs.
- Ensure unsupported files are skipped without raising fatal errors.
- Emit console output for each discovered entry with status:
  - consumed
  - skipped

Behavior details:
- Sort entries deterministically before processing/reporting.
- Keep output readable and machine-parse-friendly where practical (stable prefixes or status tokens).

## 5.3 Path Canonicalization to output/temp

Target files:
- `src/md_gen/config.py`
- `src/md_gen/foundation.py`
- Any writer modules currently receiving `im-temp`/`md-temp` paths explicitly.

Required changes:
- Derive and propagate all intermediate artifact directories from `output/temp`.
- Ensure existing behavior that skips overwrite unless requested still works.
- Ensure no stage writes intermediate files outside `output/temp`.

Likely directory strategy:
- `output/temp` for image, markdown, and JSON metadata location (or subfolder if already established)

## 5.4 Summary Prompt File Externalization

Target files:
- `src/md_gen` gateway/request builder usage points
- prompt file location under repository (to be defined, e.g., `prompts/md_gen_summary_system_prompt.txt`)

Required changes:
- Add default prompt file in repo.
- Add `--summary-prompt` CLI override.
- Implement robust fallback ladder to built-in prompt text.
- Ensure summary request builder consumes plain text prompt as `system_prompt`.

Failure handling:
- Missing/invalid prompt file must not crash if fallback exists.
- Console should indicate fallback activation to aid debugging.

## 5.5 Error and Logging Behavior

Target files:
- `src/md_gen/foundation.py`
- shared error helpers (if introduced)
- any log-file writer dependencies currently in md_gen pipeline

Required changes:
- Emit machine-readable error code + human-readable message on failures.
- Remove mandatory file-log behavior from md_gen flow.
- Preserve useful console stage reporting.

## 5.6 Shared Gateway Enforcement (New 4.3 Point)

Target files:
- All md_gen imports referencing `md_gen.gateway`
- `src/md_gen/gateway.py`

Required changes:
- Replace md_gen-local gateway imports with `common.llama_gateway` imports.
- Remove shim dependency from md_gen runtime paths.
- Delete `src/md_gen/gateway.py` alias module once imports are migrated.

Risk control:
- Update tests in same commit/phase to avoid partial-import breakage.
- Confirm all gateway symbols used by md_gen are available in common module exports.

## 5.7 Test Migration and Expansion (md_gen)

Filesystem moves:
- Move md_gen-related tests from `test/` to `test/md_gen/` first, preserving names.
- Update imports/fixtures after move.

Minimum new/updated test coverage:
- CLI argument validation (`--source`, `--output` required).
- Directory-only source validation failure.
- Output auto-create behavior.
- Non-recursive discovery and extension allow-list behavior.
- Consumed/skipped console reporting.
- Prompt file default/override/fallback behavior.
- output/temp path invariant for intermediate artifacts.
- Gateway imports resolve from `common.llama_gateway` only.

## 6. Deliverables of Phase 1

- Updated md_gen contract and path behavior implemented.
- Prompt externalization for summary complete.
- md_gen local gateway alias removed; common gateway is the only source.
- md_gen tests migrated and passing under `test/md_gen`.
- Coverage setup in place for md_gen target and threshold participation.
- README/help snippets updated for md_gen CLI contract.

## 7. Exit Criteria (Phase 1 Done)

Phase 1 is complete when:
- md_gen accepts only required `--source` and `--output`.
- md_gen no longer accepts multi-source/source-list/temp-dir/log-file args.
- md_gen intermediate artifacts are rooted under `output/temp`.
- discovery is non-recursive and reports consumed/skipped entries.
- summary prompt is file-driven with override and built-in fallback.
- all md_gen runtime imports use `common.llama_gateway`.
- `src/md_gen/gateway.py` is removed.
- md_gen tests are under `test/md_gen` and pass.

## 8. Known Risks and Mitigations

Risk: hidden runtime assumptions on old temp dirs.
Mitigation: audit stage constructors and writer entry points before final refactor.

Risk: deleting alias gateway causes import regressions.
Mitigation: run full import scan and update all references before deletion.

Risk: fallback prompt masks configuration errors.
Mitigation: emit explicit console notice when fallback path is used.

## 9. Handoff to Phase 2

Phase 1 outputs consumed by Phase 2:
- stable md_gen output-root contract with intermediate artifacts under `<output>/temp`.
- stable use of common gateway for LLM integrations.
- normalized test layout pattern for md_gen to mirror in md_mrg.
