# Wire OCR Stage

So far we have the webapp workflow layout doen with the stage button in place, but the OCR, Merge, and Rename stages are not-wire and just are simulators. This task is focus on wiring the OCR stage.

The OCR stage to comprise of the next flow
1. After the `Start` button is click and the files discovered, the `OCR` button get enabled.
2. Bt clicking the `OCR` button a two step process start
    1. We run the `md_gen.cli` coommand to generate the markdown files from the documents in the `source` folder to the `output` folder. This also will generate the `batch.json`
    2. We run then `md_mrg.cli --plan` which will take the `batch.json` to create the `batch_mrg.json` with the detected image scans groups.

There are a few updates to make to both `md_gen` and `md_mrg`, that this is how to track the progress and show it in real time in the webapp.

## Goals

- Update both `md_gen` and `md_mrg` to report the progress. For `md_gen` there will be N ocr jobs where N is the number of discovered pages (sum of each PDF's file pages and image files), this will result in N markdown files to show in the `Markdown` label in the UI. We want this number to update as the job progress (along with the progress bar). For `md_mrg` there will be Y jobs where Y is the number of image files minus 1 (since there are n-1 comparison amont n items). The label `PDF documents` is already available from the `batch.json` so there is no job in `md_mrg` for them, and the `Image Groups` are the detected groups in `md_mrg.cli --plan`. We want the `md_gen` job take 50% of the progress bar, and the `md_mrg.cli --plan` job take the other 50%.
- Find and propose the best design pattern to report the progress from the python modules, to the backend, to the frontend.
- Cancelation of this progress is not required
- Have a current image in process would be nice so we can indicate in the item list which document is currently being proceesed.
- Wire the `OCR` button to the two-step ocr flow

# Refinement Iteration 1
**Status:** PENDING USER FEEDBACK

## 1. Executive Summary
The webapp OCR stage must be converted from a simulator into a real two-step workflow that runs `md_gen.cli` followed by `md_mrg.cli --plan` against the configured workspace folders. The workflow must stream progress from the Python processing layers through the backend to the frontend so users can see Markdown generation, merge planning, overall progress, and the currently processed item in near real time.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement OCR-001:** Enable OCR Stage After Discovery
    - **Description:** The `OCR` stage button must remain unavailable until the user clicks `Start` and file discovery completes successfully for the selected workspace/source folder.
    - **Acceptance Criteria:**
        - [ ] Given the workflow has not started, When the page is displayed, Then the `OCR` button is disabled or otherwise unavailable for execution.
        - [ ] Given `Start` has been clicked, When file discovery completes successfully, Then the `OCR` button becomes enabled.
        - [ ] Given file discovery fails or finds no processable files, When discovery completes, Then the `OCR` button remains unavailable and the UI presents the failed or empty discovery state.

- **Requirement OCR-002:** Run Markdown Generation From Webapp
    - **Description:** Clicking the enabled `OCR` button must run the existing `md_gen.cli` workflow to process documents from the `source` folder into Markdown files in the `output` folder and produce `batch.json`.
    - **Acceptance Criteria:**
        - [ ] Given discovery has completed and the `OCR` button is enabled, When the user clicks `OCR`, Then the backend starts the `md_gen.cli` stage using the configured `source` and `output` paths.
        - [ ] Given `md_gen.cli` is running, When each page or image OCR job completes, Then one Markdown output is counted toward the `Markdown` label.
        - [ ] Given `md_gen.cli` completes successfully, When the stage ends, Then `batch.json` exists in the expected output location and the generated Markdown count equals the completed OCR job count.
        - [ ] Given `md_gen.cli` fails, When the failure occurs, Then the OCR workflow stops before merge planning and the UI reports the failure state.

- **Requirement OCR-003:** Run Merge Plan After Markdown Generation
    - **Description:** After successful Markdown generation, the backend must run `md_mrg.cli --plan` using the generated `batch.json` to create `batch_mrg.json` with detected image scan groups.
    - **Acceptance Criteria:**
        - [ ] Given `md_gen.cli` completed successfully and produced `batch.json`, When the OCR workflow advances, Then the backend starts `md_mrg.cli --plan` using that `batch.json`.
        - [ ] Given merge planning completes successfully, When the stage ends, Then `batch_mrg.json` exists in the expected output location.
        - [ ] Given merge planning detects image scan groups, When the UI receives the result, Then the `Image Groups` label reflects the number of detected groups.
        - [ ] Given merge planning fails, When the failure occurs, Then the UI reports the OCR workflow as failed while preserving any completed Markdown generation output.

- **Requirement OCR-004:** Report Progress From `md_gen`
    - **Description:** `md_gen` must expose progress events for N OCR jobs, where N is the total number of discovered PDF pages plus standalone image files. These events must allow the backend and frontend to update the progress bar, Markdown count, and current item indication as work completes.
    - **Acceptance Criteria:**
        - [ ] Given discovered inputs include PDFs and image files, When OCR starts, Then `md_gen` reports a total job count equal to the sum of all PDF pages and image files.
        - [ ] Given an OCR job starts, When progress is reported, Then the event identifies the current source document or page sufficiently for the frontend to highlight the active item.
        - [ ] Given an OCR job completes, When progress is reported, Then the completed Markdown count increments by one.
        - [ ] Given all OCR jobs complete, When the `md_gen` stage ends, Then the `md_gen` portion contributes exactly 50% to the overall OCR stage progress.

- **Requirement OCR-005:** Report Progress From `md_mrg --plan`
    - **Description:** `md_mrg --plan` must expose progress events for Y comparison jobs, where Y is the number of image files minus one for n sequential image comparisons. PDF document counts are read from `batch.json` and must not add merge-planning jobs.
    - **Acceptance Criteria:**
        - [ ] Given `batch.json` contains n image Markdown entries, When merge planning starts, Then the total comparison job count is `max(n - 1, 0)`.
        - [ ] Given merge planning is processing image comparisons, When each comparison completes, Then the merge-planning progress increments within the second 50% of the overall OCR stage progress.
        - [ ] Given `batch.json` includes PDF documents, When merge planning starts, Then the existing PDF document count is available to the UI without being counted as merge-planning work.
        - [ ] Given merge planning completes, When `batch_mrg.json` is available, Then the `Image Groups` label reflects the detected groups from the plan output.

- **Requirement OCR-006:** Stream Progress Through Backend To Frontend
    - **Description:** The system must use a clear progress-reporting pattern that lets CLI/module code emit structured progress events, backend workflow code aggregate those events into OCR-stage state, and the frontend render updates in real time.
    - **Acceptance Criteria:**
        - [ ] Given either Python stage emits a progress event, When the backend receives it, Then the event is normalized into workflow state containing stage name, total jobs, completed jobs, current item, counts, status, and errors when applicable.
        - [ ] Given workflow state changes during OCR execution, When the frontend is open, Then the progress bar and stage labels update without waiting for the full command to finish.
        - [ ] Given `md_gen` and `md_mrg` are also usable as CLIs, When progress reporting is added, Then existing command-line behavior remains compatible unless an explicit progress output option is introduced.
        - [ ] Given the OCR flow completes successfully, When the final event is emitted, Then the overall progress is 100% and the OCR stage status is complete.

- **Requirement OCR-007:** Preserve Existing Workflow Boundaries
    - **Description:** The implementation must reuse existing `md_gen` and `md_mrg` processing logic rather than duplicating OCR or merge-planning behavior in the webapp backend.
    - **Acceptance Criteria:**
        - [ ] Given the webapp starts the OCR stage, When processing occurs, Then OCR logic remains owned by `src/md_gen` and merge-planning logic remains owned by `src/md_mrg`.
        - [ ] Given progress support is added, When unit tests run, Then existing CLI tests for `md_gen` and `md_mrg` continue to pass or are updated only for intentional interface changes.
        - [ ] Given backend workflow tests run, When the OCR stage is executed with mocked processing, Then the backend verifies the correct two-stage order and progress aggregation.

## 3. Scope & Constraints
- **In-Scope:**
    - Wire the existing webapp `OCR` button to a real backend OCR workflow.
    - Run `md_gen.cli` first and `md_mrg.cli --plan` second.
    - Add structured progress reporting to both `md_gen` and `md_mrg`.
    - Show real-time progress updates in the frontend progress bar and labels.
    - Update Markdown count as OCR jobs complete.
    - Show PDF document count from `batch.json`.
    - Show image group count from `batch_mrg.json` after merge planning.
    - Include current item information when available so the frontend can identify the document or page being processed.
    - Add or update focused backend/frontend/unit tests for the wired OCR path.
- **Out-of-Scope:**
    - Canceling an active OCR or merge-planning run.
    - Wiring the later Merge and Rename stages beyond any state needed to reflect OCR completion.
    - Replacing the existing OCR engine, summarization behavior, merge algorithm, or file discovery strategy.
    - Adding cloud services or remote job execution.
    - Persisting long-term job history outside the existing workflow/session state unless already supported by the backend.
- **Technical Constraints / Edge Cases:**
    - The progress calculation must allocate 0-50% to `md_gen` and 50-100% to `md_mrg --plan`.
    - If there are zero OCR jobs, `md_gen` progress must avoid division-by-zero and transition deterministically to the merge-planning step or an empty-complete state.
    - If there are zero or one image files, `md_mrg --plan` must report `max(n - 1, 0)` comparison jobs and still produce a valid final plan state if the CLI supports it.
    - Progress events should be structured data, not human-readable log parsing, so backend and frontend behavior remains testable.
    - The design must preserve local/offline execution and work through the project environment.
    - Partial output from a failed `md_gen` or `md_mrg` run must not be presented as a successful completed OCR stage.

## 4. Open Design Choices (Questions for User)
- **[UX/UI]:** Should the active item highlight appear in the existing discovered document list, or should the OCR stage add a separate processing list for page/image-level work?
**User: Use the existing dicovered document list.**

- **[UX/UI]:** While `md_gen` is complete and `md_mrg --plan` is running, should the UI label the overall stage as still `OCR`, or should it visibly show a sub-step such as `Planning image groups`?
**User. Should remain the same as OCR. The user does not need to know the internal details of the multiple stages. But it would be nice to have an indicator in the existing document list which pair of documents are in the step of comparison. We can also use the statuc bar so indicate something like `Running OCR on file {filename}` and `Comparing relation of file {file-A} and {file-B}.`**

- **[Business Logic]:** If `md_gen` succeeds but `md_mrg --plan` fails, should the user be able to retry only merge planning, or should retry always rerun the full OCR stage?
**User: For simplicity not have to rerun the entire OCR stage. Later we will decide on recovery strategies.**

- **[Business Logic]:** Should standalone images and PDF pages both increment the `Markdown` label equally, or should the UI distinguish Markdown files generated from PDF pages versus image files?
**User: yes, both. A PDF with 5 pages and 3 images would produce 8 markdown files.**

- **[Technical]:** Should the backend call the existing CLI entrypoints as subprocesses, or should it call reusable Python functions inside `md_gen` and `md_mrg` with progress callbacks while keeping the CLI wrappers thin?
**User: one way would be to directly call the main() method or call the CLI in a subprocess. Choose the cleanest way for event report that keep the CLI funcionality intact.**

- **[Technical]:** What real-time transport should the webapp use for progress updates: polling the existing workflow state endpoint, Server-Sent Events, or WebSockets?
**User: I don't not, propose the best method for this application that produces the cleanest implementation base on best design patterns or methods.**

# Refinement Iteration 2
**Status:** LOCKED

## 1. Executive Summary
The OCR stage is now fully specified as a real webapp workflow that starts only after discovery succeeds, then runs Markdown generation followed by image-group merge planning. Progress must be emitted as structured events from reusable Python module functions, aggregated by the backend into workflow state, and streamed to the frontend with Server-Sent Events so the existing workflow UI updates in near real time.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement OCR-001:** Enable OCR Stage After Successful Discovery
    - **Description:** The `OCR` stage button must remain unavailable until the user clicks `Start` and file discovery completes successfully with at least one processable source item.
    - **Acceptance Criteria:**
        - [ ] Given the workflow has not started, When the page is displayed, Then the `OCR` button is disabled or unavailable.
        - [ ] Given `Start` has been clicked, When file discovery completes successfully and finds processable documents, Then the `OCR` button becomes enabled.
        - [ ] Given discovery fails or finds no processable documents, When discovery completes, Then the `OCR` button remains unavailable and the UI presents the failed or empty discovery state.
        - [ ] Given discovery has completed successfully, When the user changes settings or source paths in a way that invalidates discovery, Then the `OCR` button returns to an unavailable state until discovery is rerun successfully.

- **Requirement OCR-002:** Run Markdown Generation From The Webapp
    - **Description:** Clicking the enabled `OCR` button must start the existing Markdown generation workflow against the configured `source` folder and write Markdown output plus `batch.json` to the configured `output` folder.
    - **Acceptance Criteria:**
        - [ ] Given discovery has completed and the `OCR` button is enabled, When the user clicks `OCR`, Then the backend starts the Markdown generation stage using configured source and output paths.
        - [ ] Given Markdown generation is running, When each PDF page or standalone image OCR job completes, Then the generated Markdown count increments by one.
        - [ ] Given Markdown generation completes successfully, When the stage ends, Then `batch.json` exists in the expected output location.
        - [ ] Given Markdown generation completes successfully, When the UI receives the final generation state, Then the `Markdown` label equals the total completed OCR jobs.
        - [ ] Given Markdown generation fails, When the failure is reported, Then the OCR workflow stops before merge planning, the UI reports failure, and partial output is not presented as a completed OCR stage.

- **Requirement OCR-003:** Run Merge Planning After Markdown Generation
    - **Description:** After Markdown generation succeeds, the backend must run the existing merge-planning workflow equivalent to `md_mrg.cli --plan`, using the generated `batch.json` to create `batch_mrg.json` and detect image scan groups.
    - **Acceptance Criteria:**
        - [ ] Given Markdown generation completed successfully and produced `batch.json`, When the OCR workflow advances, Then the backend starts merge planning using that `batch.json`.
        - [ ] Given merge planning completes successfully, When the stage ends, Then `batch_mrg.json` exists in the expected output location.
        - [ ] Given merge planning detects image scan groups, When the UI receives the result, Then the `Image Groups` label reflects the number of detected groups.
        - [ ] Given merge planning starts, When `batch.json` contains PDF document entries, Then the `PDF documents` label is populated from `batch.json` and is not counted as merge-planning work.
        - [ ] Given merge planning fails after Markdown generation succeeds, When the failure is reported, Then the OCR workflow is marked failed and retry behavior reruns the full OCR stage for now.

- **Requirement OCR-004:** Expose Structured Progress Events From `md_gen`
    - **Description:** `md_gen` must expose reusable Python processing functions that accept an optional progress callback and emit structured progress events for OCR jobs without requiring the backend to parse CLI text output.
    - **Acceptance Criteria:**
        - [ ] Given discovered inputs include PDFs and image files, When Markdown generation starts, Then `md_gen` reports a total job count equal to all PDF pages plus standalone image files.
        - [ ] Given a PDF page or image OCR job starts, When progress is emitted, Then the event includes the current source document identifier and, for PDFs, page information sufficient to highlight the parent document in the discovered document list.
        - [ ] Given an OCR job completes, When progress is emitted, Then the event includes completed job count, total job count, generated Markdown count, and current item information.
        - [ ] Given all OCR jobs complete, When the final generation event is emitted, Then the generation stage reports complete and contributes exactly the first 50% of the overall OCR progress.
        - [ ] Given the existing `md_gen` CLI is used outside the webapp, When progress support is added, Then current CLI behavior remains compatible and any machine-readable progress output is opt-in.

- **Requirement OCR-005:** Expose Structured Progress Events From `md_mrg --plan`
    - **Description:** `md_mrg` must expose reusable Python planning functions that accept an optional progress callback and emit structured progress events for sequential image comparison jobs.
    - **Acceptance Criteria:**
        - [ ] Given `batch.json` contains `n` image Markdown entries, When merge planning starts, Then the total comparison job count is `max(n - 1, 0)`.
        - [ ] Given merge planning compares adjacent image candidates, When each comparison starts or completes, Then the progress event identifies both source documents being compared so the existing discovered document list can indicate the active pair.
        - [ ] Given a comparison completes, When progress is emitted, Then completed comparison count increments within the second 50% of the overall OCR progress.
        - [ ] Given there are zero or one image Markdown entries, When merge planning runs, Then it avoids division-by-zero, emits a deterministic complete state, and still writes a valid plan if supported by the existing planner.
        - [ ] Given merge planning completes, When the final planning event is emitted, Then it includes the detected image group count derived from `batch_mrg.json`.
        - [ ] Given the existing `md_mrg` CLI is used outside the webapp, When progress support is added, Then current CLI behavior remains compatible and any machine-readable progress output is opt-in.

- **Requirement OCR-006:** Aggregate OCR Progress In Backend Workflow State
    - **Description:** The backend must call reusable Python functions directly, keep CLI wrappers thin, normalize module progress callbacks into workflow state, and expose both snapshot and streaming access to that state.
    - **Acceptance Criteria:**
        - [ ] Given the webapp starts OCR, When processing begins, Then the backend invokes `md_gen` and `md_mrg` reusable functions directly rather than shelling out and parsing human-readable logs.
        - [ ] Given either processing layer emits a progress event, When the backend receives it, Then it updates workflow state with OCR status, current phase, stage totals, completed counts, current item, active comparison pair, Markdown count, PDF document count, image group count, overall percent, and errors when applicable.
        - [ ] Given `md_gen` is running, When generation progress changes, Then the backend maps generation progress to overall OCR progress from 0% through 50%.
        - [ ] Given `md_mrg` planning is running, When planning progress changes, Then the backend maps planning progress to overall OCR progress from 50% through 100%.
        - [ ] Given either sub-stage has zero work items, When overall progress is calculated, Then the backend uses a deterministic complete contribution for that sub-stage and never divides by zero.
        - [ ] Given OCR completes successfully, When the final backend state is emitted, Then OCR status is complete, overall progress is 100%, current item and active comparison pair are cleared, and final counts reflect output files.

- **Requirement OCR-007:** Stream Progress To The Frontend With Server-Sent Events
    - **Description:** The frontend must receive real-time workflow state updates through Server-Sent Events because OCR progress is one-way server-to-client communication and does not require WebSocket bidirectional messaging.
    - **Acceptance Criteria:**
        - [ ] Given OCR is running and the frontend is open, When backend workflow state changes, Then the frontend receives updates through an SSE endpoint without waiting for the full command to finish.
        - [ ] Given the SSE connection is established after OCR has already started, When the connection opens, Then the frontend receives the latest available workflow state before subsequent updates.
        - [ ] Given the SSE connection is interrupted, When the frontend reconnects or falls back to the existing state endpoint, Then it recovers the latest workflow state without restarting OCR.
        - [ ] Given no OCR job is running, When the frontend loads, Then it can still render workflow state from the existing snapshot endpoint.
        - [ ] Given cancellation is out of scope, When OCR is running, Then the frontend does not need to expose a cancel action for this iteration.

- **Requirement OCR-008:** Update Existing Workflow UI For Real OCR State
    - **Description:** The existing workflow layout must render real OCR progress while keeping the user-facing stage labeled as `OCR`, hiding internal sub-stage names from primary stage controls.
    - **Acceptance Criteria:**
        - [ ] Given OCR is running on a file or PDF page, When the UI receives current item state, Then the existing discovered document list indicates the active parent document.
        - [ ] Given merge planning is comparing two image-derived documents, When the UI receives active comparison state, Then the existing discovered document list indicates both documents in the active pair.
        - [ ] Given OCR is running, When status text is displayed, Then it may show user-friendly messages such as `Running OCR on file {filename}` or `Comparing relation of file {file-A} and {file-B}` without exposing implementation stage names as primary workflow steps.
        - [ ] Given OCR progress changes, When the frontend receives state updates, Then the progress bar, `Markdown`, `PDF documents`, and `Image Groups` labels update from real backend state.
        - [ ] Given OCR completes successfully, When final state is rendered, Then the `OCR` stage appears complete and later stages may become available only according to existing workflow rules.

- **Requirement OCR-009:** Preserve Module Boundaries And Testability
    - **Description:** OCR logic must remain owned by `src/md_gen`, merge-planning logic must remain owned by `src/md_mrg`, and the webapp backend must orchestrate the two stages without duplicating domain processing logic.
    - **Acceptance Criteria:**
        - [ ] Given the backend starts OCR, When Markdown generation occurs, Then OCR processing remains implemented in `src/md_gen`.
        - [ ] Given the backend starts merge planning, When image groups are detected, Then planning remains implemented in `src/md_mrg`.
        - [ ] Given progress support is added, When unit tests run, Then existing CLI tests continue to pass or are updated only for intentional compatible interface changes.
        - [ ] Given backend workflow tests run, When the OCR stage is executed with mocked processing callbacks, Then tests verify the two-stage order, progress aggregation, failure handling, and final counts.
        - [ ] Given frontend workflow tests run, When mocked SSE or state updates are delivered, Then tests verify progress rendering, label updates, active document highlighting, and active comparison highlighting.

## 3. Scope & Constraints
- **In-Scope:**
    - Wire the existing webapp `OCR` button to a real backend OCR workflow.
    - Enable OCR only after successful discovery with processable files.
    - Run Markdown generation first and merge planning second.
    - Refactor or expose reusable `md_gen` and `md_mrg` functions with optional progress callbacks while keeping CLI behavior intact.
    - Use structured progress events rather than human-readable log parsing.
    - Aggregate progress in backend workflow state and map `md_gen` to 0-50% and `md_mrg --plan` to 50-100%.
    - Add an SSE endpoint for live workflow progress plus snapshot-state support for initial load and recovery.
    - Update the existing frontend workflow UI to show real progress, generated Markdown count, PDF document count, image group count, active document highlighting, active comparison highlighting, and user-friendly status text.
    - Add or update focused tests for module progress events, backend orchestration, SSE/state behavior, and frontend rendering.
- **Out-of-Scope:**
    - Canceling an active OCR or merge-planning run.
    - Partial retry that resumes only merge planning after a generation success and planning failure.
    - Wiring later Merge and Rename stages beyond any existing state transitions needed after OCR completion.
    - Replacing the OCR engine, summarization behavior, merge algorithm, file discovery strategy, or document grouping rules unrelated to progress reporting.
    - Adding cloud services, remote job execution, persistent long-term job history, or multi-user job coordination.
    - Adding a separate page-level processing list; highlighting must use the existing discovered document list.
- **Technical Constraints / Edge Cases:**
    - Progress events must be structured data with stable fields suitable for backend normalization and frontend rendering.
    - Reusable module functions must be callable in-process by the backend, and CLI entrypoints must remain thin wrappers around those functions.
    - CLI progress output, if added, must be opt-in and machine-readable; default CLI behavior must remain compatible with existing tests and user expectations.
    - Overall OCR progress must allocate exactly 50% to Markdown generation and 50% to merge planning, including deterministic handling when one sub-stage has zero jobs.
    - Markdown count must treat standalone images and PDF pages equally; for example, a five-page PDF plus three standalone images produces eight Markdown outputs.
    - Merge-planning work count must be `max(n - 1, 0)` for `n` image Markdown entries and must not include PDF document count as comparison work.
    - The frontend primary stage label remains `OCR`; internal sub-stage wording may appear only in status text.
    - The implementation must remain local-first and run through the project's Python environment.
    - Failed OCR or planning runs must not be represented as successful completed OCR stages, even if partial output files exist.

**LOCKED**
