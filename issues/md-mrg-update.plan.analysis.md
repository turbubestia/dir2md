# Implementation Analysis: md-mrg-update

## 1. Architectural Impact & Data Flow
The merge stage is being re-established as a two-phase pipeline that starts from the md_gen output contract and remains fully local-first. The new behavior introduces a deterministic planning artifact for user review and a separate apply execution artifact for operational traceability.

- **Affected Subsystems:** md_mrg CLI orchestration, md_mrg planner flow, md_mrg apply flow, shared configuration loading from common.config, language model gateway integration through common.gateway, merge-stage internal documentation, merge-stage test suite.
- **Data Flow Changes:**
  - User executes md_mrg with --plan and --source.
  - Planner reads source/batch.json produced by md_gen and partitions records into image records (candidate pages) and pdf records (already complete).
  - Planner evaluates only adjacent image pairs using LlamaLanguageGateway with the required Page A/Page B prompt envelope and score extraction.
  - Planner applies abs(score) >= 5 grouping logic, including in-group reorder when score is negative, and boundary split on low score or scoring failure.
  - Planner writes source/batch_mrg.json with image groups first (including singleton groups), then original pdf records.
  - User reviews and may edit batch_mrg.json externally.
  - User executes md_mrg with --apply and --source.
  - Apply reads source/batch_mrg.json, merges each image group in listed order into deterministic merged-NNN.pdf and merger-NNN.md outputs in source, deletes only loose markdown from successfully merged groups, and leaves original images untouched.
  - Apply continues past per-group failures and writes source/batch_mrg_result.json containing per-item/group status outcomes (ok/failed) for debugging.

## 2. Component & File Impact Map

### src/md_mrg/cli.py
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Add md_mrg command-line entrypoint with mandatory --source.
  - [ ] Add mutually exclusive mandatory workflow flags: --plan and --apply.
  - [ ] Wire argument parsing to planner/apply orchestration only (no merge logic in CLI).
  - [ ] Add deterministic exit-path handling for argument/config/runtime failures.
- **Logic Modifications Required:**
  - [ ] Enforce exactly one workflow mode.
  - [ ] Validate source directory exists and dispatch selected workflow.
  - [ ] Route config validation errors to actionable user-facing diagnostics.

### src/md_mrg/planner.py
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Add batch.json loader for source folder with schema checks for documents array.
  - [ ] Add image/pdf partitioning utilities based on file_type.
  - [ ] Add adjacent-pair scoring adapter using LlamaLanguageGateway and TextRequest contract.
  - [ ] Add score parsing boundary layer for required JSON output fields and fallback failure state.
  - [ ] Add group builder that supports threshold-based growth, singleton groups, and negative-score reorder.
  - [ ] Add serializer/writer for source/batch_mrg.json with image groups first and pdf records appended after groups.
- **Logic Modifications Required:**
  - [ ] Compare only current page i to i+1 in traversal sequence.
  - [ ] Continue current group only when abs(score) >= 5.
  - [ ] When score < 0 and threshold is met, place Page B before Page A inside the active group and continue next comparison from prior Page A position as specified.
  - [ ] On score parse/gateway failure, treat boundary as failed split and continue processing later pairs.

### src/md_mrg/apply.py
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Add batch_mrg.json loader with support for mixed item shapes: group objects ({documents:[...]}) and standalone pdf document entries.
  - [ ] Add deterministic output naming sequencer for grouped outputs: merged-NNN.pdf and merger-NNN.md.
  - [ ] Add markdown concatenation flow for each group, preserving listed order.
  - [ ] Add image-to-pdf assembly flow for each group, preserving listed order.
  - [ ] Add post-success cleanup for loose markdown files in the merged group only.
  - [ ] Add result persistence writer for source/batch_mrg_result.json with per-work-item status.
- **Logic Modifications Required:**
  - [ ] Continue processing subsequent groups when one group fails.
  - [ ] Mark failed groups/work items as failed in result metadata.
  - [ ] Avoid destructive operations on failure path (do not delete source markdown for failed groups).
  - [ ] Preserve original image files unconditionally.
  - [ ] Preserve original pdf records as already complete documents in source-level results.

### src/md_mrg/__init__.py
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update module exports/metadata to reflect new public md_mrg surface (cli/planner/apply availability).
- **Logic Modifications Required:**
  - [ ] Keep package-level behavior side-effect free for import safety.

### src/common/config.py
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add md_mrg-specific config extraction/validation helpers sourced from settings.json md_mrg section.
  - [ ] Add typed settings container(s) for md_mrg score prompt path and any required md_mrg runtime options.
  - [ ] Preserve existing md_gen config assembly without behavior regressions.
- **Logic Modifications Required:**
  - [ ] Validate required md_mrg keys before planner/apply starts.
  - [ ] Reuse language_model endpoint/model/timeout/retry values for planner scoring gateway.

### data/config/settings-default.json
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Ensure md_mrg section explicitly documents required planner/apply keys and default values.
- **Logic Modifications Required:**
  - [ ] Keep backward-compatible defaults so clean bootstrap remains deterministic.

### data/config/settings.json
- **Type of Change:** Modify (if needed to stay in sync with defaults)
- **Structural Changes:**
  - [ ] Align md_mrg section shape with validated runtime expectations.
- **Logic Modifications Required:**
  - [ ] Ensure local environment remains runnable with no missing-key errors for md_mrg.

### docs/internals/md_mrg.md
- **Type of Change:** Modify (currently empty)
- **Structural Changes:**
  - [ ] Document planner/apply architecture and stage boundaries.
  - [ ] Define batch_mrg.json schema including group object shape ({documents:[...]}) and standalone pdf record handling.
  - [ ] Define batch_mrg_result.json schema and status semantics.
  - [ ] Document ordering guarantees (image groups first in plan output; in-group order controls both markdown and PDF merge order).
- **Logic Modifications Required:**
  - [ ] Capture failure-continuation semantics and non-deletion guarantees for original images.

### README.md
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update md-mrg usage documentation from legacy subcommand contract to required flag contract (--plan/--apply with mandatory --source).
  - [ ] Update merge artifact names and files (batch_mrg.json, batch_mrg_result.json, merged-NNN.pdf, merger-NNN.md).
- **Logic Modifications Required:**
  - [ ] Remove outdated references to legacy merge-plan/temp metadata workflow that no longer applies.

### test/md_mrg/test_mrg_plan.py
- **Type of Change:** Modify (substantial rewrite)
- **Structural Changes:**
  - [ ] Replace legacy expectations tied to removed modules (io/models/scorers/merge-plan.json) with planner tests aligned to batch.json -> batch_mrg.json behavior.
  - [ ] Add adjacent scoring progression cases, threshold splits, singleton groups, and image-groups-before-pdf ordering assertions.
  - [ ] Add negative-score reorder assertions matching locked rule.
- **Logic Modifications Required:**
  - [ ] Validate planner continuation on scoring/parsing failures without aborting full run.

### test/md_mrg/test_mrg_units.py
- **Type of Change:** Modify (substantial rewrite)
- **Structural Changes:**
  - [ ] Replace tests for removed edge/window graph planner with tests for sequential adjacency planner behavior.
  - [ ] Add tests for LLM prompt envelope format (Page A/Page B markers exactness).
  - [ ] Add apply-stage tests for deterministic output naming, successful markdown cleanup, failure continuation, and result-file persistence.
- **Logic Modifications Required:**
  - [ ] Verify apply never deletes source images.
  - [ ] Verify failed groups are recorded as failed while later groups still process.

### test/common/test_config.py
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Extend configuration tests to cover md_mrg-specific key presence and error-code surfaces.
- **Logic Modifications Required:**
  - [ ] Ensure md_gen tests remain valid and unaffected while adding md_mrg validation cases.

## 3. Boundary & Edge Case Analysis
- **Error Handling:**
  - Planner boundary failures (gateway errors, invalid JSON score payload, missing markdown for pair evaluation) must not abort the full planning run; they create a split boundary and continue.
  - Apply failures must be isolated per group/work item, persist failed status to batch_mrg_result.json, and continue with subsequent groups.
  - Configuration failures (missing md_mrg keys, missing score prompt path, invalid source directory) should fail fast before work starts with explicit error codes/messages.
- **Security & Permissions:**
  - No new auth scope or RBAC surfaces are introduced; module remains local filesystem + local model endpoint.
  - File writes (batch_mrg.json, batch_mrg_result.json, merged outputs) require explicit handling of overwrite/collision behavior to prevent accidental clobber.
- **Performance / Scale Impact:**
  - Planner complexity remains linear in number of image pages because only adjacent comparisons are scored.
  - Gateway calls are one per adjacent pair (n-1 for n image pages), so timeout and retry settings from language_model materially affect runtime.
  - Apply stage performs sequential file I/O and image loading; large image groups may increase memory pressure unless processed incrementally.
- **Boundary Conditions:**
  - Empty or missing documents list in batch.json should produce deterministic empty-plan behavior rather than crash.
  - All-pdf batch should produce plan output with only standalone pdf entries and no scoring calls.
  - All-image batch should still output group objects for every document, including singleton groups.
  - Negative high-confidence scores require in-group reorder without breaking traversal pointer semantics.
  - Plan/apply must operate correctly on Windows path semantics and preserve UTF-8 JSON/markdown handling.

## 4. Verification Checklist
- [ ] Verify md-mrg CLI rejects missing mode, dual modes, and missing source with clear diagnostics.
- [ ] Verify planner reads source/batch.json and writes source/batch_mrg.json.
- [ ] Verify planner scores only adjacent image pairs and never compares pdf entries.
- [ ] Verify abs(score) >= 5 grouping logic and abs(score) < 5 split logic.
- [ ] Verify negative-score reorder behavior inside active group and subsequent comparison anchor semantics.
- [ ] Verify singleton image pages are encoded as one-item group objects.
- [ ] Verify planner output always places image groups before standalone pdf entries.
- [ ] Verify planner prompt payload to LlamaLanguageGateway matches required Page A/Page B envelope exactly.
- [ ] Verify planner continues after score parse/gateway failure and records split behavior deterministically.
- [ ] Verify apply reads source/batch_mrg.json and writes merged-NNN.pdf plus merger-NNN.md per successful image group.
- [ ] Verify apply deletes only loose markdown files for successful groups.
- [ ] Verify apply does not delete original image files in any outcome.
- [ ] Verify apply continues processing remaining groups after one group fails.
- [ ] Verify apply writes source/batch_mrg_result.json for mixed success/failure runs.
- [ ] Verify docs/internals/md_mrg.md documents batch_mrg.json and batch_mrg_result.json schemas and ordering rules.
- [ ] Verify README md-mrg usage reflects required --plan/--apply flag contract and current artifact names.