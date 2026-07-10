# Issue 3 - Detailed Implementation Plan (Gateway Refactor + Merge Module)

## Purpose

Implement loose multi-page merge planning/execution with a swappable scorer, while extracting reusable LLM connectors from `md_gen` into a shared gateway module.

This plan is implementation-oriented (no code in this document) and includes phases, TODOs, validations, and exit criteria.

## Scope Summary

In scope:
- Extract shared gateway from `src/md_gen/gateway.py`.
- Introduce `LlamaLanguageGateway` for reusable text/JSON LLM calls.
- Keep OCR gateway capability reusable for `md_gen`.
- Build new `src/md_mrg` module with plan/apply workflows.
- Add swappable scorer interface with:
  - `heuristic` scorer
  - `llm` scorer using local endpoint `http://localhost:8081/v1/chat/completions`
- Select exactly one scorer per run with a command argument.
- Evolve `src/md_gen/metadata-schema.json` to support merge-batch structures and review flags.

Out of scope:
- UI wiring (frontend/backend integration)
- Model serving lifecycle

## Target Deliverables

1. Shared gateway module with reusable transport/error handling.
2. Updated `md_gen` to use shared gateway, no duplicated connector logic.
3. New `md_mrg` planning and apply workflows.
4. Swappable scorer architecture and selection flags.
5. Optional comparison notes for later manual benchmarking.
6. Updated schema and validation flow.
7. Test coverage for unit/integration/regression paths.

## Phase Plan

## Phase 0 - Baseline and Contract Freeze

### Tasks
- Confirm frozen decisions from analysis:
  - window `k=5`, threshold policy (`>=7` auto, `5/6` review, `<=4` reject)
  - markdown separator `---`
  - filename strategy `date-subject-title`
  - overwrite semantics unchanged
- Define exact target location for shared gateway module.
- Define interface contracts for scorer and gateway request/response types.
- Define schema additions:
  - batch-level wrapper support
  - per-edge `decision_status`
  - review flag properties
  - scorer metadata (`scorer_type`, `latency_ms`)

### Validation
- Design review checklist approved.
- No unresolved contract ambiguity before code changes.

### Exit Criteria
- Contract spec document section is complete and accepted.

## Phase 1 - Shared Gateway Extraction and Rename

### Tasks
- Extract gateway transport logic from `src/md_gen/gateway.py` into shared module.
- Introduce shared class names:
  - `LlamaLanguageGateway` for text/JSON calls.
  - Vision gateway class for OCR path (name can remain vision-specific).
- Preserve existing behavior:
  - retries
  - timeout handling
  - status/error mapping (`GatewayErrorCode`)
- Migrate `md_gen` calls to shared module.
- Keep temporary compatibility shim in `src/md_gen/gateway.py` only if needed to avoid broad breakage during migration.

### Validations
- Existing `md_gen` OCR and summary paths behave identically before/after extraction.
- Error categories and messages remain stable for existing tests.

### Exit Criteria
- `md_gen` no longer owns unique connector implementation.
- Shared gateway is the single source of truth for LLM transport.

## Phase 2 - md_mrg Skeleton and Planning Pipeline

### Tasks
- Create `src/md_mrg` module scaffold and CLI entrypoints:
  - `plan`
  - `apply`
- Implement planning flow skeleton:
  - load/validate metadata from `md-temp`
  - split verified-sequence vs loose fragments
  - candidate generation with bidirectional local window (`k=5`)
- Add plan artifact writing to `mg-temp` using evolved schema.

### Validations
- Planning command runs end-to-end on fixture metadata without merge inference errors.
- Verified sequences pass through untouched with deterministic ordering.

### Exit Criteria
- `md-mrg plan` produces valid batch artifact for mixed inputs.

## Phase 3 - Swappable Scorer Interface

### Tasks
- Define scorer interface contract (`EdgeScorer` style):
  - input: edge candidates + node data + config
  - output: normalized edge score records
- Implement scorer A (`heuristic`):
  - feature extraction and weighted pre-score formula
  - deterministic sorting and pruning
- Implement scorer B (`llm`) using shared `LlamaLanguageGateway`:
  - apply bridge-scoring prompt from issue request
  - parse strict JSON response (`reason`, `bridge_score`)
  - map parse/network failures to reject/retry policy
- Implement selection mode:
  - `heuristic`
  - `llm`
  - selected once per run via `--edge-scorer`

### Validations
- `llm` scorer calls only shared language gateway.
- Threshold mapping applied consistently after scorer outputs.

### Exit Criteria
- Planning can run with either scorer selected by command argument.

## Phase 4 - Chain Resolution and Decision Encoding

### Tasks
- Implement deterministic graph resolver with constraints:
  - max one outgoing per page
  - max one incoming per page
  - no cycles
- Sort edges by:
  - bridge_score desc
  - heuristic score desc (when available)
  - lexical tiebreakers
- Encode decisions in artifact:
  - `auto_merge`, `review_required`, `reject`
  - review flags for score 5/6

### Validations
- Resolver output is stable across repeated runs on same input.
- Cycles are prevented in stress fixtures.

### Exit Criteria
- Final chains and standalone pages correctly represented in plan.

## Phase 5 - Apply Workflow (Markdown/PDF/Summary/Naming)

### Tasks
- Implement markdown merge:
  - sequence order from plan
  - page separator `---`
  - merged front matter with review status
- Implement PDF merge:
  - image order from plan
  - page size policy (US-letter / US-legal / center-fit)
- Implement merged summary from snippets only.
- Implement filename proposal from summary using LLM-assisted naming guidance (`date-subject-title`).
- Enforce overwrite behavior for merged outputs.

### Validations
- Output artifacts generated correctly for reviewed and auto-merge documents.
- Existing outputs are skipped unless overwrite is enabled.

### Exit Criteria
- `md-mrg apply` produces deterministic markdown/PDF outputs and naming metadata.

## Phase 6 - Schema Evolution and Validation Tooling

### Tasks
- Update `src/md_gen/metadata-schema.json` to support:
  - prior document metadata
  - batch wrapper
  - scorer and review fields
- Add schema validation at key boundaries:
  - plan input load
  - plan output write
  - apply input load
- Add schema version marker if required for compatibility.

### Validations
- Old-format compatible inputs are accepted or translated with clear errors.
- New plan artifacts validate cleanly.

### Exit Criteria
- One unified schema supports both md_gen metadata and merge planning artifacts.

## Phase 7 - Tests and Regression Coverage

### Unit Tests
- shared gateway:
  - timeout/retry/error mapping
  - parser behavior for valid/invalid payloads
- scorer interface compliance
- heuristic feature computations and normalization
- llm scorer parser/retry behavior
- resolver cycle prevention and tie-breaking

### Integration Tests
- mixed dataset (verified PDF + loose scans)
- plan outputs for `heuristic` and `llm`
- apply outputs markdown/PDF with overwrite semantics
- `md_gen` regression after gateway extraction

### Benchmark/Evaluation Tests
- persist per-run scoring metrics:
  - total edges
  - accepted edges
  - median/p95 latency
  - total wall-clock scoring time
- optional labeled set metrics:
  - precision, recall, F1

### Exit Criteria
- All critical unit/integration tests pass.
- Regression confirms no behavior loss in `md_gen` OCR/summary paths.
- Per-run scorer metrics are captured.

## TODO Checklist

- [ ] Freeze interface and schema contract.
- [ ] Extract shared gateway and add `LlamaLanguageGateway`.
- [ ] Migrate `md_gen` calls to shared gateway.
- [ ] Scaffold `src/md_mrg` CLI and pipeline.
- [ ] Implement candidate generation and edge model.
- [ ] Implement `heuristic` scorer.
- [ ] Implement `llm` scorer on port 8081 using shared gateway.
- [ ] Wire single scorer selection by command argument.
- [ ] Implement resolver with review flag semantics.
- [ ] Implement apply flow (markdown merge, PDF merge, naming, summary).
- [ ] Evolve schema and add validation hooks.
- [ ] Add/adjust unit, integration, and regression tests.

## Validation Gates (Go/No-Go)

Gate A - Gateway extraction complete:
- `md_gen` passes gateway regression tests.
- No duplicate LLM connector code remains.

Gate B - Planning quality complete:
- Deterministic plans generated across reruns.
- `heuristic` and `llm` scorers both functional.

Gate C - Apply quality complete:
- Merged markdown and PDF outputs match plan ordering and rules.
- Review flags are preserved into output metadata.

Gate D - Evaluation complete:
- Per-run scorer metrics exist for the selected scorer.
- Team can decide default scorer using accumulated run evidence.

## Risks and Mitigations

Risk: refactor breaks `md_gen` behavior.
- Mitigation: perform extraction first with regression tests before `md_mrg` integration.

Risk: llm scorer latency is too high.
- Mitigation: keep `heuristic` default; compare it with `llm` in separate runs.

Risk: schema migration breaks old artifacts.
- Mitigation: add compatibility checks and versioned validation messages.

Risk: disagreement between scorers creates unstable decisions.
- Mitigation: preserve both scores and include review flags; keep active scorer explicit.

## Final Definition of Done

This issue is done when:
- Shared gateway refactor is complete and stable.
- `md_mrg plan` and `md_mrg apply` are operational with schema-validated artifacts.
- Two scorer implementations are selectable and benchmarkable.
- Only one scorer runs per plan invocation.
- Review semantics and overwrite rules are enforced.
- Tests pass, including `md_gen` regression and scorer comparison output generation.
