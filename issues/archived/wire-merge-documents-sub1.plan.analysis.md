# Implementation Analysis: wire-merge-documents

## 1. Architectural Impact & Data Flow
*High-level overview of how data flows through the system for this feature. Identify any new patterns or structural additions.*
- **Affected Subsystems:** `md_mrg` CLI apply workflow, merge apply result persistence, common language gateway usage, md_gen summary prompt configuration, merge unit/CLI tests.
- **Data Flow Changes:** `md-mrg --apply` reads `batch_mrg.json` -> validates final document work items -> for PDF-backed items reads the existing `summary` and Markdown companion -> for image-group items reads non-empty child summaries in plan order and sends one combined user prompt through the configured language gateway using `cfg.md_gen.prompts.summary_prompt_text` -> writes or updates exactly one final PDF and one final Markdown per successful item -> prepends the selected normalized summary as a standard `# Abstract` block to the final Markdown body -> writes `batch_mrg_result.json` with output paths, status, and the same normalized summary used in the Markdown abstract.
- **Existing Flow Preservation:** The current `src/md_mrg/apply.py` flow already owns `batch_mrg.json` reading, group Markdown merging, image-to-PDF merging, group Markdown cleanup, failure capture per group, and `batch_mrg_result.json` persistence. The feature should extend that flow in place rather than introduce a second apply pipeline.
- **New Structural Pattern:** Summary handling should become an apply-stage concern with a clear boundary between summary selection/generation, abstract block construction, target-path planning, collision validation, artifact writing, and result payload normalization.

## 2. Component & File Impact Map
*Identify the exact files that must be created, modified, or deleted, and what structural changes they require.*

### `./src/md_mrg/apply.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Replace the current group output constants `MERGED_PDF_PATTERN` and `MERGED_MD_PATTERN` with the locked `doc_merged_{index:03d}.pdf` and `doc_merged_{index:03d}.md` naming contract.
  - [ ] Stop discarding `cfg` in `run_apply`; the apply workflow now needs `cfg.language_model`, `cfg.md_gen.prompts.summary_prompt_text`, and `cfg.runtime.overwrite`.
  - [ ] Add an internal representation for each successful final output that carries item index, item type, output PDF name, output Markdown name, normalized summary, and source document data.
  - [ ] Add helper boundaries for selecting a PDF summary, collecting image-group summaries, generating an image-group overall summary, building the abstract-prefixed Markdown body, planning final artifact names, checking overwrite/collision rules, and validating one-PDF/one-Markdown cardinality.
  - [ ] Preserve existing JSON reading, document-list validation, group Markdown merge, group image PDF merge, group Markdown cleanup, per-group failure recording, and result-file writing responsibilities.
- **Logic Modifications Required:**
  - [ ] For PDF-backed items, derive the final PDF name from `source_file_name` and the final Markdown name from the same stem with `.md`, regardless of the `markdown_file` value in the input document.
  - [ ] For PDF-backed items, read the existing Markdown companion body, prepend the standard abstract block using the document `summary` verbatim, and write the final Markdown target.
  - [ ] For PDF-backed items, preserve or ensure the original PDF file remains as the single final PDF artifact for that item.
  - [ ] For image-group items, collect child `summary` values in plan order, skip missing or empty summaries, concatenate the remaining summaries into one user-content payload, and request one overall summary through the language model using the existing md_gen summary prompt.
  - [ ] For image-group items, write exactly one merged PDF and exactly one merged Markdown using `doc_merged_XXX` names where `XXX` follows group plan order with three-digit zero padding.
  - [ ] For every successful item, prepend Markdown with exactly `# Abstract`, the normalized summary content, a blank line, `---`, a blank line, and the original Markdown body.
  - [ ] Do not detect, replace, or remove any `# Abstract` section already present in the original Markdown body.
  - [ ] Apply `cfg.runtime.overwrite` before writing target Markdown/PDF/result artifacts that could collide with existing files; disabled overwrite should fail clearly before producing duplicate or partial final outputs.
  - [ ] Persist the normalized summary in `batch_mrg_result.json` for each successful PDF and image-group item, matching the abstract written to the Markdown file.
  - [ ] Keep failed group behavior explicit in the result payload, including existing `error_code`, `message`, and source documents where available.

### `./src/md_mrg/cli.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add an `--overwrite` CLI option for `md-mrg` so `build_md_mrg_config_from_args` can receive the global overwrite setting currently read with `getattr(args, "overwrite", False)`.
  - [ ] Keep the existing `--plan`/`--apply` mutual exclusion and existing language model override options intact.
- **Logic Modifications Required:**
  - [ ] Ensure `--apply --overwrite` routes through the existing config builder and reaches `run_apply` as `cfg.runtime.overwrite`.
  - [ ] Preserve existing CLI error handling for `ApplyError`, `PlannerError`, config failures, and unexpected runtime failures.

### `./src/md_gen/summarize.py`
- **Type of Change:** Modify or Reuse
- **Structural Changes:**
  - [ ] Decide whether the merge apply flow should call the existing `summarize_document` function directly or share its summary-cleaning behavior through a small reusable boundary.
  - [ ] Keep the md_gen public behavior unchanged; any change here must support reuse without changing md_gen outputs.
- **Logic Modifications Required:**
  - [ ] Preserve the current behavior of skipping empty summaries and returning a single non-empty summary verbatim when only one summary remains.
  - [ ] Ensure merged image groups with multiple non-empty summaries use the same md_gen summary prompt text and configured language model path.

### `./src/common/gateway.py`
- **Type of Change:** No direct change expected
- **Structural Changes:**
  - [ ] Continue using `LlamaLanguageGateway` and `TextRequest` for summary generation.
- **Logic Modifications Required:**
  - [ ] No new gateway behavior is required; apply should reuse the existing `system_prompt` plus `user_prompt` language request contract.

### `./src/common/config.py`
- **Type of Change:** No direct change expected, verify only
- **Structural Changes:**
  - [ ] Confirm `build_md_mrg_config_from_args` continues to populate `md_gen.prompts.summary_prompt_text`, `language_model`, and `runtime.overwrite` for md_mrg.
- **Logic Modifications Required:**
  - [ ] No new config schema is expected because the existing md_gen summary prompt and language model settings are already part of `AppConfig`.

### `./test/md_mrg/test_mrg_units.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Update existing apply tests that assert old `merged-XXX.pdf` and `merger-XXX.md` names to the new `doc_merged_XXX` contract.
  - [ ] Add focused tests for abstract block insertion on merged image Markdown.
  - [ ] Add focused tests for PDF-backed document summary reuse and PDF-stem Markdown naming.
  - [ ] Add tests that image-group summary generation skips empty/missing child summaries while preserving plan order for non-empty summaries.
  - [ ] Add tests that `batch_mrg_result.json` persists the normalized summary for each successful final document.
  - [ ] Add tests for overwrite-disabled collisions and overwrite-enabled replacement behavior.
  - [ ] Add tests for one-PDF/one-Markdown result validation and failure behavior when the plan or target paths would violate the contract.
- **Logic Modifications Required:**
  - [ ] Use a fake language gateway or monkeypatch summary boundary for deterministic image-group summary tests.
  - [ ] Verify the summary persisted in the result payload exactly matches the summary written in the Markdown abstract.
  - [ ] Preserve existing tests that prove group failures are captured and later groups continue where that behavior remains part of the apply contract.

### `./test/md_mrg/test_mrg_plan.py`
- **Type of Change:** Modify
- **Structural Changes:**
  - [ ] Add or update CLI parser/config tests for the new `md-mrg --apply --overwrite` option.
  - [ ] Keep existing tests for plan/apply dispatch and error return codes.
- **Logic Modifications Required:**
  - [ ] Verify `--overwrite` is accepted by the md_mrg parser and passed to `run_apply` through `AppConfig.runtime.overwrite`.

### `./issues/wire-merge-documents.plan.analysis.md`
- **Type of Change:** Create
- **Structural Changes:**
  - [ ] Capture the architectural impact, file impact map, boundaries, edge cases, and verification checklist for the locked requirements.

## 3. Boundary & Edge Case Analysis
*Detail how system boundaries, errors, and edge cases will be handled structurally.*
- **Error Handling:** Apply should continue using `ApplyError` with clear `error_code` values for plan-read errors, invalid plan shape, missing group Markdown/image fields, unreadable Markdown/image files, output collisions, summary-generation failures, missing PDF-backed Markdown files, and output-cardinality violations. Existing group-scoped failure recording can remain for image groups; preflight collision validation should prevent partial writes when target names are known to conflict and overwrite is disabled.
- **Language Model Boundary:** Image-group overall summary generation must use the configured language model and the existing md_gen summary system prompt. Missing or empty child summaries are skipped before the request. If no non-empty summaries remain, the apply layer needs a defined normalized empty-summary behavior that still produces a deterministic abstract block and persisted summary value.
- **PDF Boundary:** PDF-backed documents are not language summarized during apply. Their `summary` field is the source of truth for the abstract. Their final PDF identity is the existing `source_file_name`, and their final Markdown identity is the same stem with `.md`.
- **Markdown Boundary:** Abstract prepending is not idempotent against source content and should not inspect for existing abstracts in the original body. The apply-generated abstract block must be added once by the final write operation for each successful output.
- **Artifact Naming Boundary:** Image-group numbering follows plan order among group items. PDF-backed items keep original PDF names and do not consume image-group sequence numbers. The result payload should expose final artifact names consistently for both item types.
- **Overwrite and Collision Handling:** `cfg.runtime.overwrite` governs target collisions. With overwrite disabled, existing target files for final PDF/Markdown outputs should cause a clear failure before duplicate or partial final outputs are produced. With overwrite enabled, the workflow may replace target outputs according to the same file names.
- **Output Cardinality:** A successful final item must map to exactly one `.pdf` and one `.md` artifact. The apply layer should validate this at the result-contract level and by target path planning so duplicate output names across plan items are rejected or prevented.
- **Security & Permissions:** No new permission or authentication model is introduced. File writes remain local to the configured source/output directory. The implementation should continue avoiding arbitrary external services beyond the configured local-first language endpoint.
- **Performance / Scale Impact:** Image-group summary generation adds one language-model request per successful image group with at least enough non-empty summaries to require normalization. Markdown and JSON processing remain linear in the number of plan items and group children. Large summary payloads rely on the existing language gateway and model limits; no database or index changes are involved.

## 4. Verification Checklist
*A concrete list of what needs to be verified during/after implementation to ensure the analysis was correct.*
- [ ] Verify `md-mrg --apply` prepends the exact standard abstract block to every successful final Markdown output.
- [ ] Verify original Markdown bodies remain intact after the apply-generated `---` separator, including bodies that already start with `# Abstract`.
- [ ] Verify PDF-backed documents reuse the existing document `summary` verbatim and do not send a language-model summary request.
- [ ] Verify a source PDF named `my_file.pdf` produces or preserves `my_file.pdf` and writes the final Markdown as `my_file.md`.
- [ ] Verify merged image groups send all non-empty child summaries in plan order as one language-model user prompt.
- [ ] Verify missing and empty image child summaries are skipped before summary generation.
- [ ] Verify image-group summary generation uses `cfg.md_gen.prompts.summary_prompt_text` as the system prompt.
- [ ] Verify merged image outputs are named `doc_merged_001.pdf` / `doc_merged_001.md`, `doc_merged_002.pdf` / `doc_merged_002.md`, and so on by plan order.
- [ ] Verify every successful result item has exactly one final `.pdf` and one final `.md` output.
- [ ] Verify target collisions fail clearly when `cfg.runtime.overwrite` is false.
- [ ] Verify target collisions are allowed to replace existing outputs when `cfg.runtime.overwrite` is true.
- [ ] Verify `batch_mrg_result.json` is still written after apply and includes the normalized summary for each successful final document.
- [ ] Verify each persisted normalized summary exactly matches the summary in the corresponding Markdown abstract.
- [ ] Verify existing apply behavior still handles failed image groups without rewriting the apply workflow from scratch.
- [ ] Verify existing CLI dispatch, config error handling, and workflow error handling continue to return the expected exit codes.
- [ ] Run focused md_mrg tests, preferably `uv run pytest test/md_mrg`, after implementation.