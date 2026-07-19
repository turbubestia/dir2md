# Implementation Plan: wire-merge-documents

> **Core Objective:** Detailed step-by-step technical execution blueprint for implementing the requirements specified in the analysis.

## Metadata
- **Analysis Reference:** [Analysis Reference](./wire-merge-documents.plan.analysis.md)
- **Issue Name:** `wire-merge-documents`
- **Scope:** Implement merge apply final artifact wiring, summaries, abstract insertion, overwrite handling, result payloads, and focused tests.
- **Traceability Rule:** Every phase and step below references the source analysis section it implements.

## Phase 1: Lock Tests Around the New Apply Contract
*Implementing requirements from Analysis Sections 2 (`test/md_mrg/test_mrg_units.py`, `test/md_mrg/test_mrg_plan.py`), 3, and 4.*

### Steps
- **Step 1.1, Analysis Sections 2 and 4:** Update existing apply assertions in `test/md_mrg/test_mrg_units.py` from `merged-XXX.pdf` / `merger-XXX.md` to `doc_merged_XXX.pdf` / `doc_merged_XXX.md`.
- **Step 1.2, Analysis Sections 1, 2, and 4:** Add focused tests for the exact generated abstract block:
  ```text
  # Abstract

  {normalized_summary}

  ---

  {original_body}
  ```
  Verify the original body is preserved even when it already starts with `# Abstract`.
- **Step 1.3, Analysis Sections 2, 3, and 4:** Add PDF-backed item tests proving `source_file_name="my_file.pdf"` keeps `my_file.pdf`, writes final Markdown as `my_file.md` regardless of input `markdown_file`, uses the input `summary` verbatim, and does not call the language gateway.
- **Step 1.4, Analysis Sections 1, 2, and 4:** Add image-group summary tests that monkeypatch the summary boundary in `md_mrg.apply` or `md_gen.summarize.summarize_document`, then verify missing/blank child summaries are skipped and remaining summaries are passed in plan order.
- **Step 1.5, Analysis Sections 2, 3, and 4:** Add result-payload tests verifying every successful item includes `output_pdf`, `output_markdown`, and `summary`, and that the persisted summary exactly matches the abstract text in the corresponding Markdown.
- **Step 1.6, Analysis Sections 2, 3, and 4:** Add collision tests for `cfg.runtime.overwrite=False` and `True`. Use an `_cfg(source_dir, overwrite=False)` helper variant or set `dataclasses.replace(cfg.runtime, overwrite=True)` through a local test helper.
- **Step 1.7, Analysis Sections 2, 3, and 4:** Add duplicate/cardinality tests where two successful items would resolve to the same final `.pdf` or `.md` name; expect an `ApplyError` such as `output_collision` or `output_cardinality_invalid` before partial final outputs are written.
- **Step 1.8, Analysis Section 2 (`src/md_mrg/cli.py`) and Section 4:** Add CLI parser/config tests proving `--overwrite` is accepted with `--apply` and reaches `build_md_mrg_config_from_args` as `args.overwrite=True`.

### Exit Criterion
- The focused tests describe the locked behavior and fail against the current implementation for the expected reasons: old artifact names, missing abstracts, missing summary persistence, missing overwrite checks, and absent CLI `--overwrite`.

### Validation Command
```powershell
uv run pytest test/md_mrg/test_mrg_units.py test/md_mrg/test_mrg_plan.py
```

## Phase 2: Add Apply-Layer Helper Boundaries
*Implementing requirements from Analysis Sections 1, 2 (`src/md_mrg/apply.py`, `src/md_gen/summarize.py`), and 3.*

### Steps
- **Step 2.1, Analysis Section 2 (`src/md_mrg/apply.py`):** Replace constants with:
  ```python
  MERGED_PDF_PATTERN = "doc_merged_{index:03d}.pdf"
  MERGED_MD_PATTERN = "doc_merged_{index:03d}.md"
  ```
- **Step 2.2, Analysis Sections 1 and 2:** Stop deleting `cfg` in `run_apply`; retain access to `cfg.language_model`, `cfg.md_gen.prompts.summary_prompt_text`, and `cfg.runtime.overwrite`.
- **Step 2.3, Analysis Sections 1 and 2:** Add a small internal result representation near the top of `apply.py`, preferably a frozen dataclass, to avoid ad hoc dict assembly while enforcing one PDF and one Markdown per successful item:
  ```python
  @dataclass(frozen=True)
  class FinalOutput:
      item_index: int
      item_type: str
      output_pdf: str
      output_markdown: str
      summary: str
      source_documents: list[dict[str, Any]]
  ```
  Keep public `run_apply` return shape as JSON-compatible dictionaries.
- **Step 2.4, Analysis Sections 1, 2, and 3:** Add focused helpers in `apply.py` with typed signatures:
  ```python
  def _summary_from_pdf_document(document: dict[str, Any]) -> str: ...
  def _collect_group_summaries(documents: list[dict[str, Any]]) -> list[str]: ...
  def _summarize_group(config: AppConfig, documents: list[dict[str, Any]]) -> str: ...
  def _build_abstract_markdown(summary: str, body: str) -> str: ...
  def _plan_pdf_output(document: dict[str, Any]) -> tuple[str, str]: ...
  def _plan_group_output(group_index: int) -> tuple[str, str]: ...
  def _ensure_can_write(path: Path, overwrite: bool) -> None: ...
  def _validate_unique_outputs(outputs: list[tuple[str, str]]) -> None: ...
  ```
- **Step 2.5, Analysis Section 2 (`src/md_gen/summarize.py`):** Reuse `summarize_document(config, page_summaries)` from `md_gen.summarize` for group summary generation unless tests show an import-cycle problem. This preserves existing behavior: skip empty summaries, return `""` for none, return one non-empty summary verbatim, and call the language gateway only for multiple non-empty summaries.
- **Step 2.6, Analysis Sections 2 and 3:** Map language/gateway failures from `summarize_document` to `ApplyError("summary_generation_failed", ...)` inside the apply layer so group-scoped failure recording remains explicit.

### Exit Criterion
- `apply.py` has clear helper boundaries for summary selection/generation, abstract construction, output planning, collision checks, and final result normalization, without changing `run_apply`'s public entry point.

### Validation Command
```powershell
uv run pytest test/md_mrg/test_mrg_units.py -k "summary or abstract or collision or deterministic"
```

## Phase 3: Implement PDF-Backed Final Output Handling
*Implementing requirements from Analysis Sections 1, 2 (`src/md_mrg/apply.py`), 3, and 4.*

### Steps
- **Step 3.1, Analysis Sections 2 and 3:** In the non-group branch of `run_apply`, treat the item as a final PDF-backed document instead of pass-through metadata only.
- **Step 3.2, Analysis Sections 2 and 3:** Derive output names from `source_file_name`:
  ```python
  pdf_name = Path(source_file_name).name
  markdown_name = f"{Path(source_file_name).stem}.md"
  ```
  Reject missing/blank `source_file_name` with `ApplyError("pdf_source_missing", ...)`.
- **Step 3.3, Analysis Sections 2 and 3:** Read the Markdown body from the input document's existing `markdown_file` path, not from the final markdown name. Reject missing/blank `markdown_file` with `ApplyError("pdf_markdown_missing", ...)` and read failures with `ApplyError("pdf_markdown_read_failed", ...)`.
- **Step 3.4, Analysis Sections 2, 3, and 4:** Build final Markdown with `_build_abstract_markdown(_summary_from_pdf_document(item), body)` and write it to `source_dir / markdown_name` after collision validation.
- **Step 3.5, Analysis Sections 2 and 3:** Preserve the original PDF file as the final PDF artifact. If `source_dir / pdf_name` is missing, fail with `ApplyError("pdf_source_not_found", ...)`; do not copy or rename unless the final name differs from the basename, which should not occur when `Path(...).name` is used.
- **Step 3.6, Analysis Sections 2 and 4:** Append an `ok` result item with `item_type="pdf"`, `output_pdf`, `output_markdown`, `summary`, and `document` or `documents` using the existing source document data.

### Exit Criterion
- PDF-backed plan items produce exactly one final PDF identity and one abstract-prefixed Markdown file, with no language-model request.

### Validation Command
```powershell
uv run pytest test/md_mrg/test_mrg_units.py -k "pdf or abstract"
```

## Phase 4: Implement Image-Group Final Output Handling
*Implementing requirements from Analysis Sections 1, 2 (`src/md_mrg/apply.py`, `src/md_gen/summarize.py`), 3, and 4.*

### Steps
- **Step 4.1, Analysis Sections 2 and 3:** Keep existing group item detection, document-list validation, group Markdown merge, image-to-PDF merge, cleanup, and per-group failure behavior.
- **Step 4.2, Analysis Sections 2 and 3:** For each group, plan names with `_plan_group_output(group_index)` so plan-order groups produce `doc_merged_001.pdf` / `doc_merged_001.md`, `doc_merged_002.pdf` / `doc_merged_002.md`, and so on. PDF-backed items do not consume group indices.
- **Step 4.3, Analysis Sections 1, 2, and 3:** Generate the group summary before writing final Markdown. Use `_collect_group_summaries` plus `summarize_document(cfg, summaries)`, preserving missing/blank summary skipping and plan order.
- **Step 4.4, Analysis Sections 1, 2, and 3:** Merge child Markdown into a string body, prepend the abstract, then write the final group Markdown. Prefer refactoring `_merge_group_markdown` so it returns merged Markdown text or accepts an already-final body; avoid writing an intermediate final file that then must be reread.
- **Step 4.5, Analysis Sections 2 and 3:** Continue merging images into the planned PDF with `_merge_group_images_to_pdf(source_dir, documents, merged_pdf_path)`.
- **Step 4.6, Analysis Sections 2 and 3:** Only call `_cleanup_group_markdown` after both final Markdown and final PDF have been written successfully for the group.
- **Step 4.7, Analysis Sections 2 and 4:** Append an `ok` result item with `item_type="group"`, `output_pdf`, `output_markdown`, `summary`, and `documents`.
- **Step 4.8, Analysis Sections 2 and 3:** Keep failed group result payloads explicit with `status="failed"`, `error_code`, `message`, and `documents`; later groups should still run as existing tests require.

### Exit Criterion
- Successful image groups write exactly one PDF and one abstract-prefixed Markdown file using the locked names, persist the normalized summary, and still preserve failed-group continuation behavior.

### Validation Command
```powershell
uv run pytest test/md_mrg/test_mrg_units.py -k "group or summary or deterministic or continues"
```

## Phase 5: Enforce Overwrite, Collision, and Result-File Rules
*Implementing requirements from Analysis Sections 1, 2 (`src/md_mrg/apply.py`), 3, and 4.*

### Steps
- **Step 5.1, Analysis Sections 2 and 3:** Before writing a planned final Markdown or PDF, call `_ensure_can_write(path, cfg.runtime.overwrite)`. If `overwrite` is false and the path already exists as a target final artifact, raise `ApplyError("output_collision", ...)`.
- **Step 5.2, Analysis Sections 2 and 3:** Preflight duplicate planned output names across successful candidates before writes when possible. At minimum, maintain a `planned_outputs` set of lower-level path names during iteration and reject duplicate `.pdf` or `.md` targets with `ApplyError("output_cardinality_invalid", ...)`.
- **Step 5.3, Analysis Sections 2 and 3:** Treat `batch_mrg_result.json` as an overwrite-governed artifact too. If it exists and `cfg.runtime.overwrite` is false, fail with `ApplyError("output_collision", ...)` before writing it. If this conflicts with existing tests that rerun apply in the same temp directory, update those tests to opt into overwrite deliberately.
- **Step 5.4, Analysis Sections 2 and 3:** Keep partial-write risk low by validating known output targets before writing each successful item. For group failures caused by missing child files, preserve existing behavior that records the failed group and continues.
- **Step 5.5, Analysis Sections 2 and 4:** Normalize result payloads so every successful item has exactly `item_index`, `item_type`, `status="ok"`, `output_pdf`, `output_markdown`, `summary`, and source document data. Failed items keep `error_code` and `message`.

### Exit Criterion
- Output collisions and duplicate target names are rejected deterministically when overwrite is disabled, overwrite-enabled runs replace planned outputs, and successful result items expose one PDF and one Markdown artifact.

### Validation Command
```powershell
uv run pytest test/md_mrg/test_mrg_units.py -k "collision or overwrite or cardinality or result"
```

## Phase 6: Wire the CLI Overwrite Option
*Implementing requirements from Analysis Sections 2 (`src/md_mrg/cli.py`, `src/common/config.py`) and 4.*

### Steps
- **Step 6.1, Analysis Section 2 (`src/md_mrg/cli.py`):** Add `parser.add_argument("--overwrite", action="store_true", default=False)` near the existing runtime flags.
- **Step 6.2, Analysis Sections 2 and 4:** Keep existing mutually exclusive `--plan` / `--apply` behavior unchanged. The same `build_md_mrg_config_from_args(SimpleNamespace(**vars(args)))` call already reads `getattr(args, "overwrite", False)` into `cfg.runtime.overwrite`.
- **Step 6.3, Analysis Section 2 (`src/common/config.py`):** Do not change schema unless tests reveal a missing attribute. Verify `build_md_mrg_config_from_args` still populates `md_gen.prompts.summary_prompt_text`, `language_model`, and `runtime.overwrite`.
- **Step 6.4, Analysis Section 4:** Extend existing CLI tests to assert `args.overwrite is True` in a monkeypatched config builder when invoking `md-mrg --source <dir> --apply --overwrite`.

### Exit Criterion
- `md-mrg --apply --overwrite` is accepted and routes through config to `run_apply` as `cfg.runtime.overwrite=True`; existing plan/apply dispatch and error handling remain unchanged.

### Validation Command
```powershell
uv run pytest test/md_mrg/test_mrg_plan.py -k "cli or overwrite"
```

## Phase 7: Full Focused Verification and Cleanup
*Implementing requirements from Analysis Section 4.*

### Steps
- **Step 7.1, Analysis Section 4:** Run the focused merge test suite.
- **Step 7.2, Analysis Section 4:** If failures are isolated to existing assumptions changed by the new contract, update the tests to the new contract. Do not broaden refactors outside `md_mrg`, `md_gen.summarize` reuse, and focused tests.
- **Step 7.3, Analysis Section 4:** Inspect `git diff -- src/md_mrg src/md_gen test/md_mrg issues/wire-merge-documents.prompt.md` to confirm only intended files changed and source responsibilities stayed separated.
- **Step 7.4, Analysis Sections 1 and 4:** Confirm the final implementation preserves: one PDF and one Markdown per successful item, abstract summary parity with `batch_mrg_result.json`, group failure continuation, no PDF language summarization, and no abstract de-duplication.

### Exit Criterion
- All focused md_mrg tests pass and the diff matches the scoped feature described by the analysis.

### Validation Command
```powershell
uv run pytest test/md_mrg
```

## Implementation Notes for the Coding Pass
- Keep changes local to `src/md_mrg/apply.py`, `src/md_mrg/cli.py`, optionally `src/md_gen/summarize.py`, and `test/md_mrg/*` unless a failing test proves another touched boundary is required.
- Prefer small helper functions over a second apply pipeline. The existing `run_apply(source_dir: Path, cfg: AppConfig) -> dict[str, Any]` remains the owner of apply orchestration.
- Use `ApplyError` for apply contract failures, with clear `error_code` values that tests can assert.
- Do not remove or rewrite existing original Markdown body content. Abstract prepending is a final-output write concern only.
- Do not add cloud or remote dependencies; language summary generation must use the existing configured local-first language gateway path through `md_gen.summarize.summarize_document` or an equivalent apply-local wrapper using `LlamaLanguageGateway` and `TextRequest`.