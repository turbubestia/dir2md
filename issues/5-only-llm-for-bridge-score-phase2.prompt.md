# Issue 5 - Phase 2 Implementation Plan (md_mrg Contract Simplification + LLM-Only Scoring)

Analysis file: `issues/5-only-llm-for-bridge-score.plan.analysis.md`

## 1. Phase Goal

Deliver md_mrg-side contract simplification so merge planning and apply flows run from a single `--source` root, while keeping planner/apply as separate commands and enforcing LLM-only edge scoring.

## 2. Scope of This Phase

In scope:
- md_mrg CLI migration to single required `--source` flag.
- Remove md_mrg temp-dir and explicit output-dir CLI contracts.
- Planner reads metadata from `source/temp` and writes deterministic plan JSON into `source`.
- Apply reads plan JSON from `source` and writes merged artifacts to `source`.
- Keep `edge-scorer` argument but constrain to `llm` only.
- Remove heuristic scorer implementation and dead selection paths.
- Add score prompt file support with default in-repo file + `--score-prompt` override + built-in fallback.
- Ensure md_mrg uses `common.llama_gateway` only (no md_gen alias usage).
- Move md_mrg tests into `test/md_mrg`, then fix and expand.

Out of scope:
- Converting planner/apply into a single command.
- New merge heuristics or non-LLM scoring alternatives.

## 3. Preconditions and Dependencies

- Phase 1 should be complete so md_gen output is stable at `<output>/temp`.
- Deterministic plan filename rule must be confirmed (fixed name vs deterministic stem).
- Prompt default file location for score prompt must be selected in-repo.

## 4. Design Decisions Locked for This Phase

- md_mrg uses only `--source` as required root flag.
- planner and apply remain separate subcommands.
- planner input path: `source/temp`.
- planner plan output path: `source`.
- apply plan input path: `source`.
- apply merged markdown/pdf output path: `source`.
- `edge-scorer` remains visible but only accepts `llm`.
- score prompt loading order:
  1) `--score-prompt` if provided and readable
  2) default in-repo score prompt file
  3) built-in fallback prompt text

## 5. Implementation Workstreams

## 5.1 CLI Contract Refactor

Target file:
- `src/md_mrg/cli.py`

Required changes:
- `plan` command:
  - remove `--md-temp-dir` and `--mg-temp-dir`.
  - add required `--source`.
  - keep `--edge-scorer` option but with `llm` only.
  - keep rolling-window and llm connectivity/runtime flags where still relevant.
  - add `--score-prompt` override flag.
- `apply` command:
  - remove `--merge-batch-file`, `--output-dir`, `--md-temp-dir`, `--im-temp-dir` explicit-path contract.
  - add required `--source`.
  - preserve naming-model flags if still needed for filename proposal.

Derived path rules to encode in CLI or config builder:
- metadata dir = `source/temp`
- plan file dir = `source`
- merge output dir = `source`
- image temp fallback = `source/temp`-relative convention defined by pipeline

## 5.2 Planner Path and Output Contract Updates

Target files:
- `src/md_mrg/planner.py`
- `src/md_mrg/models.py`
- `src/md_mrg/io.py`

Required changes:
- Replace `PlanConfig` fields tied to `md_temp_dir`/`mg_temp_dir` with source-root model and derived paths.
- Ensure planner reads from `source/temp`.
- Ensure planner writes deterministic JSON file into `source`.
- Preserve deterministic ordering and chain-resolution behavior.
- Keep metadata compatibility checks but align error messages to new path model.

Deterministic naming policy:
- Use one explicit deterministic rule and enforce it in one place.
- Ensure overwrite behavior is consistent with configured overwrite semantics.

## 5.3 Apply Path Contract Updates

Target files:
- `src/md_mrg/apply.py`
- `src/md_mrg/io.py`

Required changes:
- Remove dependency on externally provided merge-batch absolute file path.
- Resolve merge plan path from `source` by deterministic naming rule.
- Resolve markdown/image inputs from source-root temp conventions.
- Write merged markdown/pdf to `source`.
- Keep skip-on-existing vs overwrite behavior stable.

Error-handling requirements:
- Plan-not-found and temp-input-missing scenarios must return coded errors with readable text.
- Console output should make it clear which derived paths were used.

## 5.4 Scorer Simplification to LLM-Only

Target files:
- `src/md_mrg/scorers.py`
- `src/md_mrg/planner.py`
- any scorer selection logic in models/config

Required changes:
- Remove `HeuristicEdgeScorer` implementation.
- Remove heuristic-specific thresholds and filtering branches.
- Retain `EdgeScorer` abstraction/interface to keep extensibility.
- Keep `LlmEdgeScorer` as only implementation path.
- `edge-scorer` argument must only accept `llm`; invalid values should fail in CLI parsing.

Operational note:
- Ensure LLM scoring failures are still represented deterministically in edge score payloads.

## 5.5 Score Prompt File Externalization

Target files:
- bridge-score payload builder usage in `common/llama_gateway.py` call chain (integration points)
- md_mrg CLI/config path plumbing for prompt override

Required changes:
- Add default in-repo score prompt file.
- Add `--score-prompt` override argument for planner scoring calls.
- Fallback to built-in prompt text when file is missing/unreadable.
- Keep prompt content plain text.

Validation requirements:
- Confirm prompt source precedence works exactly as defined.
- Emit console signal when fallback is used.

## 5.6 Error and Logging Contract Alignment

Target files:
- `src/md_mrg/cli.py`
- `src/md_mrg/planner.py`
- `src/md_mrg/apply.py`

Required changes:
- Normalize failures to machine-readable code + human-readable message.
- Keep console as authoritative output channel.
- Avoid reintroducing file-log dependencies.

## 5.7 Test Migration and Expansion (md_mrg)

Filesystem moves:
- Move md_mrg tests from `test/` to `test/md_mrg/` first.

Minimum new/updated test coverage:
- CLI plan/apply require `--source`.
- Planner derives `source/temp` input and `source` plan output paths.
- Apply derives plan and artifact paths from `source`.
- Deterministic plan filename behavior and overwrite policy.
- `edge-scorer` accepts only `llm`.
- Heuristic scorer code path removed/inaccessible.
- Score prompt default/override/fallback behavior.
- LLM scoring error mapping and deterministic decision status behavior.

## 6. Deliverables of Phase 2

- md_mrg CLI and config aligned to single-source-root contract.
- planner/apply path logic fully source-derived.
- heuristic scorer removed; llm-only scorer path active.
- score prompt externalization complete.
- md_mrg tests migrated and passing under `test/md_mrg`.
- README/help examples updated for md_mrg CLI.

## 7. Exit Criteria (Phase 2 Done)

Phase 2 is complete when:
- md_mrg requires `--source` only.
- planner reads `source/temp` and writes deterministic plan JSON to `source`.
- apply reads plan JSON from `source` and writes outputs to `source`.
- heuristic scorer implementation and selection path are fully removed.
- `edge-scorer` is constrained to `llm`.
- score prompt supports default file, override, and fallback.
- md_mrg tests are under `test/md_mrg` and pass.

## 8. Known Risks and Mitigations

Risk: path derivation mismatch between planner and apply.
Mitigation: centralize derived-path helpers and test both commands against same fixtures.

Risk: deterministic naming ambiguity for plan file.
Mitigation: lock one naming rule and validate in tests before broader refactor.

Risk: llm-only scoring increases dependency on endpoint availability.
Mitigation: keep strong error mapping and clear console diagnostics for gateway failures.

## 9. Cross-Phase Completion Criteria

Issue 5 is ready for implementation execution after both phases when:
- md_gen and md_mrg contracts are consistent with single-root assumptions.
- common gateway is the only LLM transport module used by both pipelines.
- tests are module-scoped and coverage gates are active at the agreed baseline.
