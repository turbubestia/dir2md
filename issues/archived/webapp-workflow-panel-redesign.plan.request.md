# WebApp Workflow Panel Redesign

In the implementation `issues\webapp-onboard-compact.prompt.md` we started the web app for this PDF and Images from a folder to markdown and document merger. In this task we want to refine the workflow page frontend to a usable state. 

In the new workflow we want the next elements

1. Row 1: At the top a bar with rounded rectangles to mark the step of the process
    1. Start: the initial buble (source folder file discovery)
    2. OCR:  the bar moves like a progress bar from start to OCR to indicate the progress of the tool `md_gen` and the `planner` flow of `md_mrg`.
    3. Merge: The bar moves from OCR to Merge to indicate the progress from the `apply` flow of `md_mrg`.
    4. Rename: The bar moves from Mrge to Rename to indicate the progress of automatic files naming (this modules if not yet develop in python, so would be non-funcional)

    Clicking any of the rounded rectangles would start its process (but only if the previous process has completed). For example, if we click on circle 2, the the OCR step 2 is executed and the step 3 is enable and 4 disabled. If we click on 1 the step 2 is enable and 3 and 4 is disable.

2. Row 2: Below this stage/progress bar we want a kind of status for with information of each step
    1. Below Start: the number of PDF discovered, the number of Image discovered
    2. Below OCR: The number of markdown files generated, the number of document groups generated (from images) and number of PDF (note this may change when the user adjust the merge batch json).
    3. Below Merge: Number of generated documents
    4. Below Rename: Number of documents renamed (rename the pdf and the markdown is one document)

3. Row 3: Here we will want three panels from left to right: List of files or documents, preview of file (PDF or images), preview of markdown text.
    For the list of documents, the content will change depending on the selected stage in the stage/progress bar.
    1. On Start: Discovered files (with only PDF or image preview) (directory list)
    2. On OCR: Procesed files (from the `batch_merge.json`) with preview of both PDF or image and the OCR text from the markdown. It would be a tree with document groups, where for images we would have a node with the images of the group as childre, single images would be a node with one child, and PDF would be a node with no childs. Here the user will have the option to move the child node (that comes from image type) inside a group or between group to change the order or grouping in case the `mg_mrg` grouping made a mistake.
    3. On Merge: A list (yes list, not tree) of merged documents from `batch_mrg_result.json` file
    4. On Rename: A document list similar from `batch_mrg_result.json` but will have the filenames updated with the renamed text (not implemented yet, and not the scope of this task to implement it).

Use the image `issues\workflow-panel.png` as reference.

## Goals

- Implement the frontend with this new layout
- Implement only the start event to show the file on the source folder. If one of the source or output folder is empty show below a statuc message. This status bar can be use to indicate also the success of each stage
- Each of the Start, OCR, Mrge, and Rename are actually button.

## No-Goals

- Wire the OCR, Merge and Rename stages
- Implement the file rename module 

---
# Refinement Iteration 1
**Status:** PENDING USER FEEDBACK

## 1. Executive Summary
This iteration formalizes the workflow page redesign for the existing web app so the user can review source discovery, OCR planning, merge output, and future rename stages from one task-oriented panel. The implementation should deliver the new frontend layout and wire only the Start stage to discover and display files from the configured source folder, while leaving OCR, Merge, and Rename process execution out of scope.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement WFP-001:** Four-Step Workflow Progress Bar
    - **Description:** The workflow page shall display a top horizontal progress control with four rounded rectangular step buttons labeled Start, OCR, Merge, and Rename. The connecting bar shall visually indicate progress from Start to OCR, OCR to Merge, and Merge to Rename as each stage becomes completed or active.
    - **Acceptance Criteria:**
        - [ ] Given the workflow page is opened, When no workflow actions have been completed, Then the Start step is available and OCR, Merge, and Rename are disabled until their prerequisite stages are satisfied.
        - [ ] Given a step is selected, When the user views the progress bar, Then the selected step is visually distinct from inactive, disabled, and completed steps.
        - [ ] Given a prior stage has completed, When the next stage becomes available, Then the connecting progress bar visually advances to that step.
        - [ ] Given the user clicks a disabled step, When the prerequisite stage has not completed, Then no process starts and the UI communicates that the step is not yet available.

- **Requirement WFP-002:** Step Button Behavior and Gating
    - **Description:** Each step circle shall function as a button. Clicking Start shall run the source file discovery flow. Clicking OCR, Merge, or Rename shall not execute backend work in this task, but the UI shall represent their disabled, placeholder, or future-action state according to prerequisite completion.
    - **Acceptance Criteria:**
        - [ ] Given the source folder and output folder are configured, When the user clicks Start, Then the frontend requests source discovery and displays discovered PDF and image files.
        - [ ] Given Start has completed successfully, When the workflow state updates, Then OCR is enabled and Merge and Rename remain disabled.
        - [ ] Given the user clicks Start after downstream stage state exists, When discovery runs again, Then OCR remains the next enabled stage and Merge and Rename are reset or disabled for the current workflow.
        - [ ] Given OCR, Merge, or Rename is clicked in this task, When the stage is not wired for execution, Then the UI does not attempt to run the corresponding Python module.

- **Requirement WFP-003:** Per-Stage Status Metrics Row
    - **Description:** The second row shall show summary metrics aligned under each workflow step. Metrics shall reflect available data for the current task and show zero, placeholder, or unavailable values when the underlying stage is not wired yet.
    - **Acceptance Criteria:**
        - [ ] Given Start discovery succeeds, When the status metrics row is displayed, Then the Start section shows the number of discovered PDF files and discovered image files.
        - [ ] Given OCR data is available from existing files or future workflow state, When OCR metrics are shown, Then the OCR section can show markdown files generated, image document groups generated, and PDF count.
        - [ ] Given Merge data is available from `batch_mrg_result.json`, When Merge metrics are shown, Then the Merge section can show the number of generated documents.
        - [ ] Given Rename is not implemented, When Rename metrics are shown, Then the Rename section shows a non-functional or zero-state count without implying backend rename support exists.

- **Requirement WFP-004:** Three-Panel Workflow Workspace
    - **Description:** The third row shall provide three panels from left to right: a stage-dependent file or document list, a source preview panel for PDF or image files, and a markdown preview panel for OCR or merged text. The panels shall update based on the selected workflow stage.
    - **Acceptance Criteria:**
        - [ ] Given Start is selected, When files have been discovered, Then the left panel lists discovered source PDFs and images and selecting an item updates the file preview panel.
        - [ ] Given Start is selected, When a selected item is a PDF or image, Then the file preview panel displays an appropriate preview or fallback state and the markdown preview panel remains empty or unavailable.
        - [ ] Given OCR is selected in a future wired state, When `batch_merge.json` is available, Then the left panel represents processed files as a document-group tree.
        - [ ] Given Merge is selected in a future wired state, When `batch_mrg_result.json` is available, Then the left panel represents merged documents as a flat list, not a tree.
        - [ ] Given Rename is selected in a future wired state, When renamed output metadata becomes available, Then the left panel can display the renamed document list without requiring rename implementation in this task.

- **Requirement WFP-005:** OCR Stage Group Tree Design
    - **Description:** The OCR stage list design shall support a document-group tree derived from `batch_merge.json`, including image groups with child image nodes, single-image groups with one child, and PDFs as leaf nodes without children. The UI shall anticipate manual regrouping and ordering of image children, but backend persistence of those edits is not required unless already available.
    - **Acceptance Criteria:**
        - [ ] Given an OCR batch contains an image document group, When OCR stage data is rendered, Then the group appears as a parent node and its images appear as ordered child nodes.
        - [ ] Given an OCR batch contains a single image, When OCR stage data is rendered, Then it appears as a group with one child image node.
        - [ ] Given an OCR batch contains a PDF, When OCR stage data is rendered, Then it appears as a node without child nodes.
        - [ ] Given an image child node is moved in the UI in a future editing flow, When grouping is adjusted, Then the UI design supports moving the child within a group or between groups.

- **Requirement WFP-006:** Start Stage Discovery and Empty Folder Status
    - **Description:** The Start stage shall be the only stage wired to backend behavior in this task. It shall discover PDF and image files from the configured source folder and show status feedback when the source folder or output folder is empty or missing.
    - **Acceptance Criteria:**
        - [ ] Given the source folder is configured and contains supported files, When Start is clicked, Then the discovered PDF and image files appear in the Start list with counts in the Start metrics.
        - [ ] Given the source folder is empty or contains no supported files, When Start is clicked, Then a status message appears below the workflow controls explaining that no source PDF or image files were found.
        - [ ] Given the output folder is empty, When Start is clicked or the workflow validates folders, Then a status message appears below the workflow controls indicating the output folder has no workflow output yet.
        - [ ] Given discovery completes successfully, When the workflow state updates, Then the status message can show success information for the Start stage.
        - [ ] Given discovery fails because a configured folder is missing or inaccessible, When Start is clicked, Then the UI shows an error status message and does not enable downstream stages.

- **Requirement WFP-007:** Visual Reference and Existing App Integration
    - **Description:** The redesigned workflow page shall follow the layout intent of `issues/workflow-panel.png` while fitting the existing frontend architecture and style conventions. The implementation shall refine the usable workflow page rather than create a marketing page or unrelated navigation surface.
    - **Acceptance Criteria:**
        - [ ] Given the workflow page loads on desktop, When the user views the page, Then the rows appear in the requested order: step progress bar, per-stage status metrics, and three-panel workspace.
        - [ ] Given the page is viewed in the existing app shell, When the workflow layout renders, Then it remains consistent with existing settings, API, and component patterns.
        - [ ] Given the viewport changes to a narrower width, When the workflow page is rendered, Then the three panels remain usable without overlapping text or controls.

## 3. Scope & Constraints
- **In-Scope:**
    - Frontend redesign of the workflow page using a four-step workflow progress control.
    - Stage buttons for Start, OCR, Merge, and Rename with prerequisite-based enablement.
    - Status metrics row for Start, OCR, Merge, and Rename.
    - Three-panel workspace for list/tree, file preview, and markdown preview.
    - Start-stage backend integration for source folder discovery only.
    - Status messaging below the workflow controls for empty source folder, empty output folder, success, and discovery errors.
    - Placeholder UI states for OCR, Merge, and Rename where execution is intentionally not wired.
    - Layout inspired by `issues/workflow-panel.png`.
    - **Out-of-Scope:**
    - Running `md_gen` OCR processing from the frontend.
    - Running the `md_mrg` planner or apply flow from the frontend.
    - Implementing automatic rename logic or a Python rename module.
    - Persisting manual OCR grouping edits unless existing APIs already support it.
    - Building full PDF rendering, image editing, or markdown editing capabilities beyond preview states needed for the redesigned workflow.
    - **Technical Constraints / Edge Cases:**
    - The implementation must respect existing module boundaries: OCR and merge logic remain in their Python modules and should not be duplicated in the frontend.
    - Folder discovery should use the configured source and output folders rather than hard-coded paths.
    - The UI must handle missing configuration, missing folders, empty folders, unsupported files, inaccessible paths, and stale output artifacts gracefully.
    - Rename is explicitly non-functional in this task and must be represented as future or disabled functionality.
    - Existing generated files such as `batch_merge.json` and `batch_mrg_result.json` may be absent; the UI must display empty or unavailable states rather than failing.
    - The typo variants "Mrge" and "mg_mrg" in the raw request are interpreted as "Merge" and `md_mrg`.

## 4. Open Design Choices (Questions for User)
- **[UX/UI]:** Should OCR, Merge, and Rename buttons be visible-but-disabled until wired, or should OCR become enabled after Start but show a "not implemented yet" status when clicked?
**User: For visual test should be functional but not wire to any backend event. They progress would be completed in a few second to animate the progress bar and see if it is working and have the progress bar animation in place.**

- **[UX/UI]:** For the Start preview panel, should PDFs/images be rendered inline in the browser when possible, or is a metadata-only preview acceptable for the first usable version?
**User: If preview the PDF is not posible then just metadata for now, images should have no problem rendering. If to render the PDF we need a package propose one so I can decide to use it or no.**

- **[Business Logic]:** When Start is rerun after previously generated output exists, should the UI preserve existing OCR/Merge metrics from output files or reset all downstream metrics to unavailable?
**User: To keep it seem let restart all later process until I decide the expected behavior or persistance rule.**

- **[Technical]:** Should this task add a new backend discovery endpoint if one does not already exist, or should the frontend call an existing settings/workflow endpoint only?
**User: create a backend enpoint that uses the `src/md_gen/discovery.py` module to find the files, this way we don't duplicate logic.**

- **[Technical]:** Should manual OCR image regrouping be purely visual in this redesign, or should it update `batch_merge.json` once the UI interaction exists?
**User: Should update `batch_merge.json` only when Merge is click and the mergin process start since it uses this same file as the merge batch information.**

---
# Refinement Iteration 2
**Status:** LOCKED

## 1. Executive Summary
This iteration locks the workflow panel redesign requirements after incorporating the answered design choices. The frontend shall deliver the four-stage workflow layout, wire only Start to a real backend discovery endpoint that reuses `src/md_gen/discovery.py`, and simulate OCR, Merge, and Rename progression for visual validation without invoking backend processing.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement WFP-001:** Four-Step Workflow Progress Control
    - **Description:** The workflow page shall display a top horizontal progress control with four rounded rectangular step buttons labeled Start, OCR, Merge, and Rename. The connecting bar shall animate between steps as stages complete, whether completion comes from real Start discovery or simulated placeholder stages.
    - **Acceptance Criteria:**
        - [ ] Given the workflow page is opened, When no workflow action has run, Then Start is enabled and OCR, Merge, and Rename are unavailable until their prerequisites are satisfied.
        - [ ] Given Start completes successfully, When the workflow state updates, Then OCR becomes enabled and the progress bar visually advances through the Start completion state.
        - [ ] Given OCR, Merge, or Rename is enabled and clicked, When the placeholder stage runs, Then the UI animates progress for a few seconds and marks that stage complete without calling OCR, merge, or rename backend modules.
        - [ ] Given a step is selected, active, complete, inactive, or unavailable, When the progress control is rendered, Then each state is visually distinguishable.
        - [ ] Given the user clicks an unavailable step, When prerequisite stages are incomplete, Then no stage starts and the status area communicates that the step is not yet available.

- **Requirement WFP-002:** Start Discovery Endpoint
    - **Description:** The backend shall expose a workflow discovery endpoint for the Start stage. The endpoint shall use the existing `src/md_gen/discovery.py` module for supported PDF and image discovery instead of duplicating discovery rules in the webapp layer.
    - **Acceptance Criteria:**
        - [ ] Given configured source and output folders exist, When the frontend starts discovery, Then it calls the new backend endpoint and receives discovered source files plus folder status information.
        - [ ] Given the source folder contains supported PDFs or images, When discovery completes, Then the response includes file metadata sufficient for the Start list and preview panel.
        - [ ] Given the source folder is empty or contains no supported files, When discovery completes, Then the response indicates that no source PDF or image files were found.
        - [ ] Given the output folder is empty, When discovery completes, Then the response includes an output-empty status so the frontend can show that no workflow output exists yet.
        - [ ] Given a configured folder is missing or inaccessible, When discovery is requested, Then the endpoint returns a clear error and the frontend does not enable downstream stages.

- **Requirement WFP-003:** Step Button Behavior and Reset Rules
    - **Description:** Each step shall be a button. Start shall run real discovery and reset later workflow state; OCR, Merge, and Rename shall be interactive visual placeholders only for this task.
    - **Acceptance Criteria:**
        - [ ] Given source and output folders are configured, When the user clicks Start, Then discovered source files appear and downstream OCR, Merge, and Rename placeholder state is reset.
        - [ ] Given Start is rerun after OCR, Merge, or Rename placeholder state exists, When discovery starts again, Then OCR becomes the only next available downstream step after Start succeeds and Merge/Rename are reset.
        - [ ] Given OCR is clicked after Start completion, When the placeholder animation finishes, Then Merge becomes enabled and Rename remains unavailable.
        - [ ] Given Merge is clicked after OCR placeholder completion, When the placeholder animation finishes, Then Rename becomes enabled.
        - [ ] Given Rename is clicked after Merge placeholder completion, When the placeholder animation finishes, Then Rename is marked complete without implying a Python rename module exists.

- **Requirement WFP-004:** Per-Stage Metrics Row
    - **Description:** The second row shall show metrics aligned under Start, OCR, Merge, and Rename. Start metrics shall use real discovery data; OCR, Merge, and Rename metrics shall show zero, placeholder, or simulated values appropriate to their visual-only state.
    - **Acceptance Criteria:**
        - [ ] Given Start discovery succeeds, When metrics render, Then Start shows discovered PDF count and discovered image count.
        - [ ] Given Start has not completed, When OCR, Merge, and Rename metrics render, Then they show unavailable or zero-state values without suggesting real processing occurred.
        - [ ] Given OCR placeholder completes, When metrics render, Then OCR may show visual placeholder counts derived from current UI state and clearly remain frontend-only.
        - [ ] Given Merge placeholder completes, When metrics render, Then Merge may show a visual generated-document count without reading or writing merge outputs unless already supported by existing data.
        - [ ] Given Rename is not implemented, When Rename metrics render, Then the renamed document count remains zero or placeholder-only.

- **Requirement WFP-005:** Three-Panel Workflow Workspace
    - **Description:** The third row shall contain three panels from left to right: a stage-dependent file or document list, a source file preview panel, and a markdown preview panel. Panel content shall switch with the selected workflow step.
    - **Acceptance Criteria:**
        - [ ] Given Start is selected and discovery has returned files, When the user selects a file in the left panel, Then the preview panel updates for that PDF or image and the markdown panel shows an empty or unavailable state.
        - [ ] Given a selected Start item is an image, When preview is available, Then the image renders inline in the preview panel.
        - [ ] Given a selected Start item is a PDF, When browser-native or existing app preview is not available, Then the preview panel shows file metadata instead of requiring a new PDF rendering package.
        - [ ] Given a richer PDF preview requires an added dependency, When implementation reaches that choice, Then the dependency shall be proposed for user approval before adoption.
        - [ ] Given OCR is selected, When placeholder or existing batch data is displayed, Then the left panel uses a document-group tree design.
        - [ ] Given Merge is selected, When placeholder or existing result data is displayed, Then the left panel uses a flat list, not a tree.
        - [ ] Given Rename is selected, When placeholder rename data is displayed, Then it uses a merged-document-style list with future renamed filenames represented as unavailable or placeholder values.

- **Requirement WFP-006:** OCR Group Tree and Future Regrouping Behavior
    - **Description:** The OCR stage design shall anticipate `batch_merge.json` document groups and future manual regrouping of image children, but this task shall not persist regrouping changes or run merge processing.
    - **Acceptance Criteria:**
        - [ ] Given an OCR batch contains an image group, When OCR data is rendered, Then the group appears as a parent node and images appear as ordered child nodes.
        - [ ] Given an OCR batch contains a single image group, When OCR data is rendered, Then it appears as a parent node with one child image.
        - [ ] Given an OCR batch contains a PDF, When OCR data is rendered, Then it appears as a leaf node with no children.
        - [ ] Given the UI supports moving image children in a future interaction, When the user changes grouping or order, Then those changes are intended to update `batch_merge.json` only when Merge is clicked and real merge processing begins in a later task.
        - [ ] Given this task does not wire Merge, When OCR grouping UI is shown, Then no `batch_merge.json` persistence is required.

- **Requirement WFP-007:** Status Messaging
    - **Description:** A status message area below the workflow controls shall communicate discovery success, empty folder states, unavailable stages, placeholder stage progress, and errors.
    - **Acceptance Criteria:**
        - [ ] Given Start discovery finds supported files, When the request succeeds, Then the status area reports discovery success with a concise summary.
        - [ ] Given the source folder has no supported files, When Start completes, Then the status area explains that no source PDF or image files were found.
        - [ ] Given the output folder has no workflow output, When Start validates folders, Then the status area indicates the output folder is empty.
        - [ ] Given OCR, Merge, or Rename is clicked as a placeholder stage, When the animation runs and completes, Then the status area indicates that the stage is simulated for visual testing and not wired to backend processing.
        - [ ] Given discovery fails, When an error response is returned, Then the status area shows a readable error and downstream steps remain unavailable.

- **Requirement WFP-008:** Existing App Integration and Responsive Layout
    - **Description:** The redesigned workflow page shall match the intent of `issues/workflow-panel.png` while fitting the existing webapp shell, API style, and component conventions.
    - **Acceptance Criteria:**
        - [ ] Given the workflow page loads on desktop, When rendered, Then rows appear in order: progress control, metrics/status row, and three-panel workspace.
        - [ ] Given the page is displayed inside the existing app shell, When rendered, Then it remains consistent with current settings and API interaction patterns.
        - [ ] Given the viewport narrows, When the workflow page is rendered, Then panels and controls remain usable without overlapping text or controls.
        - [ ] Given generated files such as `batch_merge.json` or `batch_mrg_result.json` are absent, When placeholder stages are viewed, Then the UI shows empty or unavailable states instead of failing.

## 3. Scope & Constraints
- **In-Scope:**
    - Frontend workflow layout with four stage buttons: Start, OCR, Merge, and Rename.
    - Animated progress bar behavior for real Start completion and simulated OCR, Merge, and Rename completion.
    - Start-stage backend discovery endpoint using `src/md_gen/discovery.py`.
    - Source and output folder validation/status reporting through the Start flow.
    - Stage metrics row with real Start counts and placeholder or unavailable downstream metrics.
    - Three-panel workspace for stage-specific list/tree, source preview, and markdown preview states.
    - Inline image preview for discovered images.
    - PDF metadata fallback when PDF preview is not available without adding a package.
    - Reset of OCR, Merge, and Rename UI state whenever Start is rerun.
- **Out-of-Scope:**
    - Running `md_gen` OCR processing from the frontend.
    - Running the `md_mrg` planner or apply flow from the frontend.
    - Implementing automatic rename logic or a Python rename module.
    - Adding a PDF rendering package without user approval.
    - Persisting OCR grouping edits during this task.
    - Updating `batch_merge.json` before a future real Merge action begins.
    - Building image editing, markdown editing, or full document review workflows beyond the required previews and placeholders.
- **Technical Constraints / Edge Cases:**
    - Discovery rules must remain centralized in `src/md_gen/discovery.py`.
    - The frontend must not duplicate OCR, merge, or rename business logic.
    - The workflow must handle missing configuration, missing folders, inaccessible folders, empty source folders, empty output folders, unsupported file types, and absent generated JSON artifacts.
    - Placeholder OCR, Merge, and Rename interactions must be clearly represented as visual test behavior.
    - The typo variants "Mrge", "Merge", and `mg_mrg` in earlier text are normalized to "Merge" and `md_mrg`.

**LOCKED**
