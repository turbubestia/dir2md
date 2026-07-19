# Merge Document with Summary

We need to verify that when documents are merge with `md_mrg.cli --apply` and the final markdown is produce it include the document summary at the top.

## Goald

- When image groups are merged, the individual summaries must be pass to the language LLM to generate and overal summary. We use the same summary prompt we used in `md_gen`. The request to the language model should append all individual sumaries into one user content text.
- The PDF markdown must be read, insert at the begining the summary and write it back.
- At the end of `md_mrg.cli --apply` we should have for every document exactly one pdf and one markdown documents.
- pdf documents keeps the original pdf name, so if the pdf is names `my_file.pdf` then the markdown will be `my_file.md`
- For document image groups we name then sequentially `doc_merged_XXX.pdf` and `doc_merged_XXX.md`, where `XXX` is a 0-paddded number like `001`, `023`, or `435`.

## Summary format

The summary must have this format

```
# Abstract
{sumary content}

---

```

So after the `---` the original markdown text starts.

## No Goal

- Update the webapp or md_gen is not part of this task.

---

# Refinement Iteration 1
**Status:** PENDING USER FEEDBACK

## 1. Executive Summary
This change updates the `md_mrg.cli --apply` merge workflow so every produced Markdown document begins with a normalized abstract section. For merged image groups, the workflow must combine the existing per-image summaries and send them to the same language-model summary prompt used by `md_gen`, then prepend the resulting overall summary to the merged Markdown output.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement R1:** Generate Overall Summary for Merged Image Groups
	- **Description:** When `md_mrg.cli --apply` merges a document made from image groups, it must collect the individual image summaries, concatenate them into a single user-content payload, and request one overall summary from the language model using the same summary system prompt used by `md_gen`.
	- **Acceptance Criteria:**
		- [ ] Given an image document group with individual summaries, When `md_mrg.cli --apply` processes the group, Then it sends all individual summaries in one user-content text to the configured language model.
		- [ ] Given the summary request is made for an image document group, When the system prompt is selected, Then it uses the existing `md_gen` summary prompt without introducing a separate merge-summary prompt.
		- [ ] Given the language model returns an overall summary, When the merged Markdown is written, Then the overall summary is inserted before the original merged Markdown body.

- **Requirement R2:** Prepend Abstract Section to Final Markdown
	- **Description:** Every final Markdown document produced by `md_mrg.cli --apply` must begin with a standard abstract block followed by the original Markdown content.
	- **Acceptance Criteria:**
		- [ ] Given a final Markdown document is produced, When the file is written, Then its first lines match the format `# Abstract`, the summary content, a blank line, `---`, a blank line, and then the original Markdown text.
		- [ ] Given an existing Markdown body, When the abstract is prepended, Then the original body content remains intact after the separator.
		- [ ] Given the summary content is generated or retrieved, When written to Markdown, Then it appears exactly once at the top of the document.

- **Requirement R3:** Preserve PDF-to-Markdown Naming for Original PDFs
	- **Description:** For source documents that are already PDFs, the final PDF keeps the original PDF filename and the final Markdown uses the same base filename with the `.md` extension.
	- **Acceptance Criteria:**
		- [ ] Given a source PDF named `my_file.pdf`, When `md_mrg.cli --apply` completes, Then the final PDF is named `my_file.pdf` and the final Markdown is named `my_file.md`.
		- [ ] Given a source PDF name contains valid filesystem characters, When output files are produced, Then the filename stem is preserved for both PDF and Markdown outputs.

- **Requirement R4:** Sequential Naming for Merged Image Documents
	- **Description:** For final documents created from merged image groups, output filenames must use the sequential `doc_merged_XXX` naming convention for both PDF and Markdown files.
	- **Acceptance Criteria:**
		- [ ] Given one or more image document groups are merged, When `md_mrg.cli --apply` writes outputs, Then each final PDF is named `doc_merged_XXX.pdf` and its Markdown companion is named `doc_merged_XXX.md`.
		- [ ] Given sequential merged image documents are produced, When numbering is assigned, Then `XXX` is zero-padded to three digits, such as `001`, `023`, or `435`.
		- [ ] Given a final image-group document is produced, When output validation is performed, Then exactly one PDF and exactly one Markdown file exist for that document.

- **Requirement R5:** Final Output Cardinality
	- **Description:** At the end of `md_mrg.cli --apply`, every final document must have exactly one corresponding PDF and one corresponding Markdown document.
	- **Acceptance Criteria:**
		- [ ] Given any final document in the apply plan, When `md_mrg.cli --apply` completes successfully, Then there is exactly one `.pdf` output and exactly one `.md` output for that document.
		- [ ] Given duplicate or missing output files would be produced, When the apply workflow validates outputs, Then the workflow must fail clearly or prevent the invalid output state.

## 3. Scope & Constraints
- **In-Scope:**
	- Update `md_mrg.cli --apply` behavior for final Markdown abstract insertion.
	- Generate an overall language-model summary for merged image groups from their individual summaries.
	- Use the existing `md_gen` summary prompt for image-group overall summaries.
	- Ensure final PDF and Markdown output naming follows the requested conventions.
	- Add or update tests for merge apply behavior, summary insertion, output naming, and one-PDF/one-Markdown cardinality.
- **Out-of-Scope:**
	- Webapp changes.
	- `md_gen` behavior changes, except reusing its existing summary prompt as an input to `md_mrg`.
	- New prompt design or prompt tuning beyond using the existing summary prompt.
	- Cloud-only assumptions or non-local workflow changes.
- **Technical Constraints / Edge Cases:**
	- The implementation must remain local-first and use existing configuration/gateway mechanisms for language-model calls.
	- Existing Markdown content must not be lost or duplicated when the abstract block is prepended.
	- Output naming must avoid producing multiple Markdown files for a single final document.
	- The workflow should define behavior for absent, empty, or failed individual summaries before implementation.
	- The workflow should define numbering order and collision handling for `doc_merged_XXX` outputs before implementation.

## 4. Open Design Choices (Questions for User)
- **[Business Logic]:** For original PDF documents, should the abstract be generated from an existing per-document summary, from the full Markdown content, or only inserted when a summary already exists?
**User: for PDF abstract there is already a single document summary that can be copied verbatim.**

- **[Business Logic]:** If one or more image summaries are missing or empty, should `md_mrg.cli --apply` fail, skip missing summaries, or produce a fallback abstract?
**User. For now we just skip the empties or missing.**

- **[Business Logic]:** Should `doc_merged_XXX` numbering be based on the merge plan order, source discovery order, final document order, or existing output filenames?
**User: For now just use the plan oder.**

- **[Technical]:** If a target output filename already exists, should the apply workflow overwrite it, fail, or choose the next available sequential number?
**User: We can use the override global setting as flag.**

- **[Technical]:** Should the abstract insertion be idempotent by replacing an existing `# Abstract` block at the top, or should the workflow assume final Markdown files do not already contain an abstract?
**User: Now, no replacing in the original markdowns, this is our summary and we don't care if the document, like a paper, have an abstract.**

---

# Refinement Iteration 2
**Status:** OPENED

## 1. Executive Summary
This change finalizes the `md_mrg.cli --apply` merge workflow so every final document produces exactly one PDF and one Markdown file, and every Markdown file begins with a standardized abstract block. PDF-backed documents reuse their existing single-document summary verbatim, while image-group documents generate one overall summary by sending the non-empty individual summaries to the configured language model with the existing `md_gen` summary prompt.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement R1:** Prepend Standard Abstract to Every Final Markdown
	- **Description:** Every Markdown document produced by `md_mrg.cli --apply` must begin with the merge workflow's own abstract block before the original Markdown body. The workflow must prepend this block without attempting to detect, remove, or replace any existing `# Abstract` section already present in the original document content.
	- **Acceptance Criteria:**
		- [ ] Given any final Markdown document produced by `md_mrg.cli --apply`, When the file is written, Then the first lines are exactly `# Abstract`, the selected summary content, a blank line, `---`, a blank line, and then the original Markdown body.
		- [ ] Given the original Markdown body already begins with `# Abstract`, When the merge workflow prepends its summary, Then the original body remains intact after the workflow's `---` separator.
		- [ ] Given a summary is available or generated for a final document, When the Markdown output is inspected, Then the merge workflow's abstract block appears exactly once at the top.

- **Requirement R2:** Reuse Existing Summary for PDF-Backed Documents
	- **Description:** For final documents sourced from an original PDF, the abstract content must be copied verbatim from the existing single-document summary associated with that PDF. The final PDF must preserve the original PDF filename, and the final Markdown must use the same filename stem with the `.md` extension.
	- **Acceptance Criteria:**
		- [ ] Given a source PDF named `my_file.pdf` with an existing document summary, When `md_mrg.cli --apply` completes, Then the final PDF is named `my_file.pdf` and the final Markdown is named `my_file.md`.
		- [ ] Given a PDF-backed document has an existing summary, When its final Markdown is produced, Then that summary is copied verbatim into the abstract block without an additional language-model summary request.
		- [ ] Given a valid source PDF filename, When output files are produced, Then the filename stem is preserved for both the PDF and Markdown outputs.

- **Requirement R3:** Generate Overall Summary for Merged Image Groups
	- **Description:** For final documents created from merged image groups, `md_mrg.cli --apply` must collect all non-empty individual image summaries in plan order, concatenate them into one user-content payload, and request one overall summary from the configured language model using the same summary system prompt used by `md_gen`. Missing or empty individual summaries must be skipped.
	- **Acceptance Criteria:**
		- [ ] Given an image document group with multiple non-empty individual summaries, When `md_mrg.cli --apply` processes the group, Then it sends those summaries together in one language-model request as the user content.
		- [ ] Given one or more individual image summaries are missing or empty, When the overall summary payload is prepared, Then missing or empty summaries are skipped and the remaining non-empty summaries are still used.
		- [ ] Given the image-group overall summary request is made, When the system prompt is selected, Then it uses the existing `md_gen` summary prompt and does not introduce a separate merge-summary prompt.
		- [ ] Given the language model returns an overall summary, When the merged Markdown is written, Then that overall summary is inserted in the standard abstract block before the original merged Markdown body.

- **Requirement R4:** Name Merged Image Outputs Sequentially by Plan Order
	- **Description:** For final documents created from merged image groups, output filenames must use the sequential `doc_merged_XXX` naming convention for both PDF and Markdown files. Numbering must follow the merge plan order and use three-digit zero padding.
	- **Acceptance Criteria:**
		- [ ] Given one or more image document groups are merged, When `md_mrg.cli --apply` writes outputs, Then each final PDF is named `doc_merged_XXX.pdf` and its Markdown companion is named `doc_merged_XXX.md`.
		- [ ] Given multiple merged image documents are produced, When sequence numbers are assigned, Then numbering follows plan order and uses three digits, such as `001`, `023`, or `435`.
		- [ ] Given a final image-group document is produced, When output validation runs, Then exactly one PDF and exactly one Markdown file exist for that document.

- **Requirement R5:** Enforce One PDF and One Markdown per Final Document
	- **Description:** At the end of a successful `md_mrg.cli --apply` run, each final document in the apply plan must have exactly one corresponding `.pdf` output and one corresponding `.md` output. Existing target filename collisions must be governed by the configured global overwrite setting.
	- **Acceptance Criteria:**
		- [ ] Given any final document in the apply plan, When `md_mrg.cli --apply` completes successfully, Then there is exactly one `.pdf` output and exactly one `.md` output for that document.
		- [ ] Given a target output filename already exists and global overwrite is enabled, When `md_mrg.cli --apply` writes outputs, Then the existing target file may be overwritten according to that setting.
		- [ ] Given a target output filename already exists and global overwrite is disabled, When `md_mrg.cli --apply` would write that file, Then the workflow fails clearly or prevents the invalid output state before producing duplicate or partial outputs.
		- [ ] Given duplicate or missing output files would result from the apply plan, When output validation is performed, Then the workflow fails clearly or prevents the invalid output state.

## 3. Scope & Constraints
- **In-Scope:**
	- Update `md_mrg.cli --apply` behavior for final Markdown abstract insertion.
	- Reuse existing PDF document summaries verbatim for PDF-backed final Markdown abstracts.
	- Generate one overall summary for merged image groups from non-empty individual summaries.
	- Reuse the existing `md_gen` summary prompt for image-group overall summary generation.
	- Apply the requested final output naming rules for original PDFs and merged image groups.
	- Enforce or validate the one-PDF and one-Markdown output cardinality for every final document.
	- Add or update tests for summary insertion, PDF summary reuse, image-group summary generation, output naming, overwrite behavior, and output cardinality.
- **Out-of-Scope:**
	- Webapp changes.
	- Changes to `md_gen` behavior beyond reusing its existing summary prompt from `md_mrg`.
	- New prompt design, prompt tuning, or a new merge-specific summary prompt.
	- Cloud-only assumptions or workflows that require external services beyond the existing configured gateway behavior.
- **Technical Constraints / Edge Cases:**
	- The implementation must remain local-first and use existing configuration and gateway mechanisms for language-model calls.
	- Abstract insertion must preserve the complete original Markdown body after the `---` separator.
	- The workflow must skip missing or empty individual image summaries when building the image-group overall summary payload.
	- Image-group output numbering must follow plan order.
	- Target filename collision behavior must respect the configured global overwrite setting.
	- The workflow must avoid producing multiple Markdown files or multiple PDF files for a single final document.

## User Notes

- There is already an implementation of `md_mrg.cli --apply` that is tested, we need to make sure we don't rewrite it from scratch. Also the --apply flow saves a file `batch_mrg_result.json` with the merge results. This will have the normalized summary.

---

# Refinement Iteration 3
**Status:** LOCKED

## 1. Executive Summary
This iteration keeps the locked merge-summary behavior from Iteration 2 and formalizes the implementation constraint that the existing tested `md_mrg.cli --apply` workflow must be extended rather than rewritten. The apply flow must also persist the normalized summary information in `batch_mrg_result.json` alongside the final one-PDF and one-Markdown outputs.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement R1:** Prepend Standard Abstract to Every Final Markdown
	- **Description:** Every Markdown document produced by `md_mrg.cli --apply` must begin with the merge workflow's own abstract block before the original Markdown body. The workflow must prepend this block without attempting to detect, remove, or replace any existing `# Abstract` section already present in the original document content.
	- **Acceptance Criteria:**
		- [ ] Given any final Markdown document produced by `md_mrg.cli --apply`, When the file is written, Then the first lines are exactly `# Abstract`, the selected summary content, a blank line, `---`, a blank line, and then the original Markdown body.
		- [ ] Given the original Markdown body already begins with `# Abstract`, When the merge workflow prepends its summary, Then the original body remains intact after the workflow's `---` separator.
		- [ ] Given a summary is available or generated for a final document, When the Markdown output is inspected, Then the merge workflow's abstract block appears exactly once at the top.

- **Requirement R2:** Reuse Existing Summary for PDF-Backed Documents
	- **Description:** For final documents sourced from an original PDF, the abstract content must be copied verbatim from the existing single-document summary associated with that PDF. The final PDF must preserve the original PDF filename, and the final Markdown must use the same filename stem with the `.md` extension.
	- **Acceptance Criteria:**
		- [ ] Given a source PDF named `my_file.pdf` with an existing document summary, When `md_mrg.cli --apply` completes, Then the final PDF is named `my_file.pdf` and the final Markdown is named `my_file.md`.
		- [ ] Given a PDF-backed document has an existing summary, When its final Markdown is produced, Then that summary is copied verbatim into the abstract block without an additional language-model summary request.
		- [ ] Given a valid source PDF filename, When output files are produced, Then the filename stem is preserved for both the PDF and Markdown outputs.

- **Requirement R3:** Generate Overall Summary for Merged Image Groups
	- **Description:** For final documents created from merged image groups, `md_mrg.cli --apply` must collect all non-empty individual image summaries in plan order, concatenate them into one user-content payload, and request one overall summary from the configured language model using the same summary system prompt used by `md_gen`. Missing or empty individual summaries must be skipped.
	- **Acceptance Criteria:**
		- [ ] Given an image document group with multiple non-empty individual summaries, When `md_mrg.cli --apply` processes the group, Then it sends those summaries together in one language-model request as the user content.
		- [ ] Given one or more individual image summaries are missing or empty, When the overall summary payload is prepared, Then missing or empty summaries are skipped and the remaining non-empty summaries are still used.
		- [ ] Given the image-group overall summary request is made, When the system prompt is selected, Then it uses the existing `md_gen` summary prompt and does not introduce a separate merge-summary prompt.
		- [ ] Given the language model returns an overall summary, When the merged Markdown is written, Then that overall summary is inserted in the standard abstract block before the original merged Markdown body.

- **Requirement R4:** Name Merged Image Outputs Sequentially by Plan Order
	- **Description:** For final documents created from merged image groups, output filenames must use the sequential `doc_merged_XXX` naming convention for both PDF and Markdown files. Numbering must follow the merge plan order and use three-digit zero padding.
	- **Acceptance Criteria:**
		- [ ] Given one or more image document groups are merged, When `md_mrg.cli --apply` writes outputs, Then each final PDF is named `doc_merged_XXX.pdf` and its Markdown companion is named `doc_merged_XXX.md`.
		- [ ] Given multiple merged image documents are produced, When sequence numbers are assigned, Then numbering follows plan order and uses three digits, such as `001`, `023`, or `435`.
		- [ ] Given a final image-group document is produced, When output validation runs, Then exactly one PDF and exactly one Markdown file exist for that document.

- **Requirement R5:** Enforce One PDF and One Markdown per Final Document
	- **Description:** At the end of a successful `md_mrg.cli --apply` run, each final document in the apply plan must have exactly one corresponding `.pdf` output and one corresponding `.md` output. Existing target filename collisions must be governed by the configured global overwrite setting.
	- **Acceptance Criteria:**
		- [ ] Given any final document in the apply plan, When `md_mrg.cli --apply` completes successfully, Then there is exactly one `.pdf` output and exactly one `.md` output for that document.
		- [ ] Given a target output filename already exists and global overwrite is enabled, When `md_mrg.cli --apply` writes outputs, Then the existing target file may be overwritten according to that setting.
		- [ ] Given a target output filename already exists and global overwrite is disabled, When `md_mrg.cli --apply` would write that file, Then the workflow fails clearly or prevents the invalid output state before producing duplicate or partial outputs.
		- [ ] Given duplicate or missing output files would result from the apply plan, When output validation is performed, Then the workflow fails clearly or prevents the invalid output state.

- **Requirement R6:** Preserve Existing Apply Workflow and Result File Contract
	- **Description:** The implementation must extend the existing tested `md_mrg.cli --apply` workflow in place instead of replacing it with a new apply implementation. The apply result artifact `batch_mrg_result.json` must continue to be written and must include the normalized summary selected or generated for each final document.
	- **Acceptance Criteria:**
		- [ ] Given the existing `md_mrg.cli --apply` flow is invoked, When this change is implemented, Then the current tested apply responsibilities remain intact and are extended only where needed for summaries, naming, and validation.
		- [ ] Given `md_mrg.cli --apply` completes successfully, When `batch_mrg_result.json` is inspected, Then it contains the merge results with the normalized summary for each final document.
		- [ ] Given PDF-backed and image-group documents are processed, When the result file is written, Then each final document's persisted summary matches the summary prepended to its Markdown abstract block.

## 3. Scope & Constraints
- **In-Scope:**
	- Update the existing `md_mrg.cli --apply` behavior for final Markdown abstract insertion.
	- Reuse existing PDF document summaries verbatim for PDF-backed final Markdown abstracts.
	- Generate one overall summary for merged image groups from non-empty individual summaries.
	- Reuse the existing `md_gen` summary prompt for image-group overall summary generation.
	- Apply the requested final output naming rules for original PDFs and merged image groups.
	- Enforce or validate the one-PDF and one-Markdown output cardinality for every final document.
	- Preserve the existing tested apply workflow and continue writing `batch_mrg_result.json`.
	- Persist the normalized summary in `batch_mrg_result.json` for each final document.
	- Add or update tests for summary insertion, PDF summary reuse, image-group summary generation, output naming, overwrite behavior, output cardinality, and result-file summary persistence.
- **Out-of-Scope:**
	- Webapp changes.
	- Rewriting `md_mrg.cli --apply` from scratch.
	- Changes to `md_gen` behavior beyond reusing its existing summary prompt from `md_mrg`.
	- New prompt design, prompt tuning, or a new merge-specific summary prompt.
	- Cloud-only assumptions or workflows that require external services beyond the existing configured gateway behavior.
- **Technical Constraints / Edge Cases:**
	- The implementation must remain local-first and use existing configuration and gateway mechanisms for language-model calls.
	- Abstract insertion must preserve the complete original Markdown body after the `---` separator.
	- The workflow must skip missing or empty individual image summaries when building the image-group overall summary payload.
	- Image-group output numbering must follow plan order.
	- Target filename collision behavior must respect the configured global overwrite setting.
	- The workflow must avoid producing multiple Markdown files or multiple PDF files for a single final document.
	- The normalized summary persisted in `batch_mrg_result.json` must stay consistent with the abstract written to the corresponding Markdown file.

**LOCKED**
