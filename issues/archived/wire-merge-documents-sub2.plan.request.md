# Wire Merge Document In the UI

Now we want to wite the `Merge` button in the webapp workflow to `md_mrg.cli --apply` module. In the `OCR` stage we end up with a `batch_mrg.json` file, but the user had the option to change the groups or order, so before starting the merge process we need to rewrite the `batch_mrg.json` with the user modification.

While the merge is in process we keep the group list and add pending status to all of then, the current document or group being process get highligthed with the running status. Finished documents or groups get a `done` status in green. (Similar when the OCR state start and we use the discovered list).

Only when the merge finished, we switch to the merge results list where we get the items from the `batch_mrg_result.json` file. This will tell us the pdf file and the markdown files for their preview. So here we will have only pdf to preview, no images.

We need to make sure that when the `md_mrg.cli --apply` finished, the PDF files from the source folder are copied (not moved) to the output folder. If previous request indicated a move, then this task overwrite that rule. It must be copied so the user has the chance to start the process again if he deems it necesary.

Now the progress bar needs to move from the `OCR` to the `Merge` buttons.

---

# Refinement Iteration 1
**Status:** PENDING USER FEEDBACK

## 1. Executive Summary
This change wires the webapp workflow `Merge` action to the existing `md_mrg.cli --apply` merge pipeline while preserving user edits to OCR document grouping and ordering. The UI must show merge progress against the editable group list, then switch to result previews only after merge completion using `batch_mrg_result.json`, with source PDFs copied into the output folder rather than moved.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement R1:** Merge button starts the markdown merge pipeline
	- **Description:** The webapp workflow `Merge` button must invoke the backend merge process backed by `md_mrg.cli --apply` for the current OCR batch.
	- **Acceptance Criteria:**
		- [ ] Given OCR has completed and a `batch_mrg.json` file exists, When the user clicks `Merge`, Then the backend starts the merge process using the same apply behavior as `md_mrg.cli --apply`.
		- [ ] Given merge is already running, When the user clicks `Merge` again, Then the app prevents a duplicate merge job for the same workflow run.
		- [ ] Given merge cannot start because required OCR batch files are missing or invalid, When the user clicks `Merge`, Then the UI reports the failure and does not switch to merge results.

- **Requirement R2:** Persist user-edited groups before merge starts
	- **Description:** Before invoking merge, the app must rewrite `batch_mrg.json` from the current UI state so user modifications to document groups and ordering are included in the merge input.
	- **Acceptance Criteria:**
		- [ ] Given the user has changed group membership or ordering after OCR, When `Merge` starts, Then `batch_mrg.json` is overwritten with the current group tree before the merge command is invoked.
		- [ ] Given `batch_mrg.json` is rewritten, When `md_mrg.cli --apply` reads the file, Then it receives the same group order and item order shown in the UI at merge start.
		- [ ] Given the rewrite fails, When merge is requested, Then the merge process is not started and the UI displays an actionable error.

- **Requirement R3:** Show merge progress on the group list during processing
	- **Description:** While merge is running, the UI must keep the OCR group list visible and decorate each group or document with merge status.
	- **Acceptance Criteria:**
		- [ ] Given merge has started, When the merge status view is displayed, Then all groups or documents initially show a pending status.
		- [ ] Given a specific group or document is being processed, When progress updates are received, Then that item is highlighted with a running status.
		- [ ] Given a group or document finishes successfully, When progress updates are received, Then that item shows a green `done` status.
		- [ ] Given merge is still running, When partial output files exist, Then the UI remains on the group progress list and does not switch to the final results list.

- **Requirement R4:** Move the workflow progress indicator to the Merge stage
	- **Description:** During merge execution, the workflow progress bar must be associated with the `Merge` button or stage rather than the `OCR` stage.
	- **Acceptance Criteria:**
		- [ ] Given merge is running, When the workflow header or stage controls are visible, Then progress is displayed on the `Merge` stage.
		- [ ] Given OCR has completed and merge is running, When the workflow stage state is rendered, Then the `OCR` stage no longer owns the active progress indicator.
		- [ ] Given merge completes or fails, When the workflow state updates, Then the `Merge` stage progress indicator reaches the corresponding terminal state.

- **Requirement R5:** Switch to merge results only after merge completion
	- **Description:** The UI must switch from the group progress list to the merge results list only after the merge apply process completes and `batch_mrg_result.json` is available.
	- **Acceptance Criteria:**
		- [ ] Given merge completes successfully, When `batch_mrg_result.json` is read, Then the UI displays merge result items from that file.
		- [ ] Given merge is incomplete, When the UI refreshes, Then the UI continues showing the merge progress list instead of final results.
		- [ ] Given `batch_mrg_result.json` is missing or malformed after merge completion, When the backend loads results, Then the UI displays an error state instead of an empty successful result list.

- **Requirement R6:** Merge result previews support PDFs and Markdown only
	- **Description:** Merge results must provide preview access for source PDFs and generated Markdown files as described by `batch_mrg_result.json`; image preview behavior from OCR results does not apply to this stage.
	- **Acceptance Criteria:**
		- [ ] Given merge results are shown, When a result item is selected, Then the available preview inputs are the PDF file and associated Markdown files from `batch_mrg_result.json`.
		- [ ] Given result preview controls are rendered, When the result file type is evaluated, Then image-specific preview options are not shown for merge results.

- **Requirement R7:** Copy source PDFs to the output folder after merge
	- **Description:** When `md_mrg.cli --apply` completes, PDF files from the source folder must be copied into the output folder and must remain in the source folder. This requirement supersedes any prior request to move source PDFs.
	- **Acceptance Criteria:**
		- [ ] Given merge completes successfully, When output folder contents are inspected, Then each source PDF used by the merge exists in the output folder.
		- [ ] Given source PDFs are copied to output, When the original source folder is inspected, Then the original PDFs still exist there.
		- [ ] Given a PDF already exists in the output folder, When merge attempts to copy the source PDF, Then the copy behavior is deterministic and does not silently remove or corrupt either file.

## 3. Scope & Constraints
- **In-Scope:**
	- Webapp backend endpoint or workflow action for starting merge from the UI.
	- Serialization of the current editable OCR group tree back into `batch_mrg.json` before merge starts.
	- Merge-stage progress reporting and UI status decoration for pending, running, done, and terminal error states.
	- Reading `batch_mrg_result.json` after successful merge completion and presenting PDF plus Markdown previews.
	- Ensuring source PDFs are copied, not moved, to the merge output folder.
- **Out-of-Scope:**
	- Changing the OCR pipeline behavior except where needed to hand off its editable group state to merge.
	- Adding image previews to merge results.
	- Reworking the `md_mrg` scoring, grouping, or markdown consolidation algorithm beyond integration needs.
	- Cloud execution, remote storage, or multi-user job orchestration.
- **Technical Constraints / Edge Cases:**
	- The UI-edited group model must preserve enough fields to regenerate a valid `batch_mrg.json` compatible with `md_mrg.cli --apply`.
	- Merge should not start from stale on-disk group data if the in-memory UI state has unsaved edits.
	- Long-running merge work should not block the web server request thread; the UI needs polling, streaming, or another existing progress mechanism.
	- Failed merge jobs must leave enough state for the user to inspect the error and rerun after corrections.
	- PDF copy behavior must handle filename collisions in the output folder deterministically.

## 4. Open Design Choices (Questions for User)
- **[UX/UI]:** Should merge progress statuses be displayed at the group level only, at the individual source-document level, or both when the merge process exposes enough detail?
**User: at group level.**

- **[UX/UI]:** After a merge failure, should the UI remain on the progress group list with failed items marked, or switch to a dedicated error/result state?
**User: For now move on in the process, the apply system will indicate a flag in the `bat_mrg_result.json` if there were an errot. Also we can place the group/document with a red text label status `failed`.**

- **[Business Logic]:** If a PDF filename already exists in the output folder, should the app overwrite it, skip it if identical, or create a unique filename?
**User: Moving on we will overrwire by default, but this logic if handled by `md_mrg.cli --apply`, not the backend or frontend of the webapp.**

- **[Technical]:** Should the backend call the `md_mrg.cli --apply` implementation through an internal Python function if available, or execute the CLI entry point as a subprocess to preserve exact command behavior?
**User: it should be called in the same when the `OCR` stage call to `md_gen.cli` and `md_mrg.cli --plan.**

## **User** Notes

When the merge process start we must ignore mouse event in the workflow panel in the same way as we doo when the `OCR` process is runnint.

---

# Refinement Iteration 2
**Status:** LOCKED

## 1. Executive Summary
This iteration locks the UI merge workflow requirements after incorporating the user's answers to the open design choices. The `Merge` action must persist the edited OCR group order, invoke the merge apply pipeline using the same backend execution pattern as the existing OCR and merge-plan stages, show group-level merge progress, and switch to result previews only after `batch_mrg_result.json` is produced.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement R1:** Merge button starts the apply pipeline
	- **Description:** The webapp workflow `Merge` button must start the current batch merge process backed by `md_mrg.cli --apply`, using the same backend invocation pattern already used when the workflow calls `md_gen.cli` and `md_mrg.cli --plan`.
	- **Acceptance Criteria:**
		- [ ] Given OCR has completed and a valid `batch_mrg.json` file exists, When the user clicks `Merge`, Then the backend starts the apply merge process for the current workflow run.
		- [ ] Given merge is already running for the current workflow run, When the user clicks `Merge` again, Then the app prevents a duplicate merge job.
		- [ ] Given required OCR batch files are missing or invalid, When the user clicks `Merge`, Then the merge process is not started and the UI displays an actionable error.
		- [ ] Given the workflow already has an established backend command execution mechanism for OCR and merge planning, When merge apply is wired, Then it uses that same mechanism instead of introducing an unrelated execution path.

- **Requirement R2:** Persist edited groups before merge starts
	- **Description:** Before invoking merge apply, the backend must rewrite `batch_mrg.json` from the current editable group tree so user changes to group membership and ordering are the source of truth for the merge input.
	- **Acceptance Criteria:**
		- [ ] Given the user has edited group membership or ordering after OCR, When `Merge` starts, Then `batch_mrg.json` is overwritten with the group tree currently shown in the UI before `md_mrg.cli --apply` begins.
		- [ ] Given `batch_mrg.json` is rewritten, When the merge apply process reads it, Then group order and document order match the UI state at merge start.
		- [ ] Given rewriting `batch_mrg.json` fails, When merge is requested, Then merge apply is not started and the UI reports the rewrite failure.
		- [ ] Given the UI has unsaved in-memory edits, When merge starts, Then stale on-disk group data is not used as the merge input.

- **Requirement R3:** Show group-level merge progress
	- **Description:** While merge is running, the UI must keep the OCR group list visible and decorate groups with merge statuses. Progress is tracked at group level only.
	- **Acceptance Criteria:**
		- [ ] Given merge has started, When the merge progress view is displayed, Then every group initially shows a pending status.
		- [ ] Given a group is currently being processed, When progress updates are received, Then that group is highlighted with a running status.
		- [ ] Given a group finishes successfully, When progress updates are received, Then that group shows a green `done` status.
		- [ ] Given a group fails during merge processing, When progress updates or final result metadata identify the failure, Then that group shows a red `failed` status label.
		- [ ] Given merge is still running, When partial output files exist, Then the UI remains on the group progress list and does not switch to the final results list.

- **Requirement R4:** Associate active progress with the Merge stage
	- **Description:** During merge execution, the workflow progress indicator must belong to the `Merge` stage rather than the completed `OCR` stage.
	- **Acceptance Criteria:**
		- [ ] Given merge is running, When the workflow header or stage controls are visible, Then active progress is displayed on the `Merge` stage.
		- [ ] Given OCR has completed and merge is running, When the workflow state is rendered, Then the `OCR` stage no longer owns the active progress indicator.
		- [ ] Given merge completes, When workflow state updates, Then the `Merge` stage reaches a completed terminal state.
		- [ ] Given merge fails or completes with failed group metadata, When workflow state updates, Then the `Merge` stage reaches the appropriate terminal state while preserving failure visibility in the group/result data.

- **Requirement R5:** Disable workflow panel mouse interaction during merge
	- **Description:** When merge processing starts, the workflow panel must ignore mouse interaction in the same way it does while OCR processing is running.
	- **Acceptance Criteria:**
		- [ ] Given merge is running, When the user attempts to interact with controls in the workflow panel, Then mouse events are ignored or disabled consistently with the OCR-running behavior.
		- [ ] Given merge completes or reaches a terminal failure state, When the workflow panel is rendered again, Then normal mouse interaction is restored where appropriate.
		- [ ] Given the workflow panel is non-interactive during merge, When status updates arrive, Then the UI still updates progress and status labels.

- **Requirement R6:** Switch to merge results only after apply completion
	- **Description:** The UI must switch from the group progress list to the merge results list only after the merge apply process finishes and `batch_mrg_result.json` is available for loading.
	- **Acceptance Criteria:**
		- [ ] Given merge completes, When `batch_mrg_result.json` is read successfully, Then the UI displays merge result items from that file.
		- [ ] Given merge is incomplete, When the UI refreshes, Then it continues showing the group progress list instead of final results.
		- [ ] Given `batch_mrg_result.json` is missing or malformed after merge completion, When the backend loads results, Then the UI displays an error state instead of an empty successful result list.
		- [ ] Given merge completes with one or more failed groups recorded in `batch_mrg_result.json`, When results are displayed, Then the process still advances to the result stage and exposes the failure status from the result file.

- **Requirement R7:** Merge result previews support PDFs and Markdown only
	- **Description:** Merge results must provide preview access for source PDF files and generated Markdown files described by `batch_mrg_result.json`; image preview behavior from OCR results does not apply to this stage.
	- **Acceptance Criteria:**
		- [ ] Given merge results are shown, When a result item is selected, Then the available preview inputs are the source PDF and associated Markdown files from `batch_mrg_result.json`.
		- [ ] Given result preview controls are rendered, When the result file type is evaluated, Then image-specific preview controls are not shown for merge results.
		- [ ] Given a result item references missing preview files, When the user selects it, Then the UI reports the missing file condition without presenting image preview fallbacks.

- **Requirement R8:** Copy source PDFs through merge apply output behavior
	- **Description:** When merge apply completes, source PDFs used by the merge must exist in the output folder while remaining in the source folder. Filename collision behavior is handled by `md_mrg.cli --apply`, which overwrites by default.
	- **Acceptance Criteria:**
		- [ ] Given merge completes successfully, When output folder contents are inspected, Then each source PDF used by the merge exists in the output folder.
		- [ ] Given source PDFs are copied to output, When the original source folder is inspected, Then the original PDFs still exist there.
		- [ ] Given a PDF with the same name already exists in the output folder, When merge apply copies the source PDF, Then `md_mrg.cli --apply` applies its default overwrite behavior.
		- [ ] Given the webapp backend triggers merge apply, When PDF copy behavior is needed, Then the backend/frontend do not implement separate duplicate copy or collision logic outside the apply pipeline.

## 3. Scope & Constraints
- **In-Scope:**
	- Webapp workflow action or endpoint for starting merge apply from the `Merge` button.
	- Serialization of the current editable OCR group tree back into `batch_mrg.json` before merge apply starts.
	- Group-level merge progress states: pending, running, done, and failed.
	- Moving the active workflow progress indicator from `OCR` to `Merge` during merge execution.
	- Disabling or ignoring workflow panel mouse interaction while merge is running, matching existing OCR-running behavior.
	- Reading `batch_mrg_result.json` after merge apply finishes and presenting PDF plus Markdown result previews.
	- Ensuring PDF copy behavior is provided by `md_mrg.cli --apply` and keeps original source PDFs in place.
- **Out-of-Scope:**
	- Changing OCR behavior except where needed to hand off edited group state to merge.
	- Displaying merge progress below group level.
	- Adding image previews to merge results.
	- Reworking merge scoring, grouping, or markdown consolidation algorithms beyond integration needs.
	- Implementing PDF overwrite/collision rules in the webapp backend or frontend outside the apply pipeline.
	- Cloud execution, remote storage, or multi-user job orchestration.
- **Technical Constraints / Edge Cases:**
	- The UI-edited group model must preserve all fields needed to regenerate a valid `batch_mrg.json` compatible with `md_mrg.cli --apply`.
	- Merge must not start from stale on-disk group data when the UI has newer edited group state.
	- Merge work must not block the web server request thread; it should follow the existing workflow job/progress pattern used by OCR and merge planning.
	- Failed groups should be visible through red `failed` labels, while overall flow can still advance to result display when `batch_mrg_result.json` is produced.
	- `batch_mrg_result.json` is the authoritative source for final merge result items, preview file references, and merge failure flags after apply completion.
	- PDF copy overwrite behavior is owned by `md_mrg.cli --apply`; the webapp should rely on that behavior rather than duplicating it.

**LOCKED**