# Issue 15 Sub-Issue 1 - Create OCR Module

In previous issue we have created a working `md_gen` and `md_mrg` modules. However we found the architecture not very appropieate for the intended workflow. In this issue we look to refactor the reasterizer/resizer module into one, and create the ocr_processor. Next we outline how the workflow should be handled and the modules for it to work.

# Overview

The high level OCR process works as follow

1. From the command line (The `cli` module) build a configuration class with the user provided argument as high priority.
2. The `config` modules creates the file `data/config/settings.json` with default values if it does not exist, or directly loads it if in place. The the configuration is updated with the user provided argument, such that the cli arguments takes priority.
3. Then start the discovery phase where we look in the mandatory `source` path argument (single level, no path traversal) and find for `pdf` and images `png,jpg,jpeg` files. This files are ordered by thei file name lexicography. One catch here is numers in the file name must be understand as whole, for example `file2.pdf` goes before `file10.pdf` because 2 is less than ten, where regular character per character check would place then otherwise beacuse 2 is larger than 1. All this files are save into a `FileItem` list.
4. For every PDF item in the `FileItem` list we do the next process:
    1. Rasterize page `i` as an image with the right size for the OCR (with max_edge_size proeprty)
    2. Send the rasterized image `i` to the OCR model and append the markdown text to the output markdown file.
    3. Make a summary of this page text with the Language model and append it to a list of summary strings
    4. go to the next page `i = i + 1` and repeat from one until each page is processed
    5. after all files were processed, take all summaries and using the language LLM model make a single summary of all the PDF (if there is only page in the PDF just use the first summary).
5. After a PDF is processed, save in a dict list (WorkItem list) a metadata object with the file type and relevant file information including the summary, the index from discovery, the summary, and the output markdown file.
6. For eavery image item we do the same as step 4 except we directly resize the image (no rasterization needed here) and the page count would always be one.
7. We save workitem list as a single json that describe the batch process.

We see the different from older implementation that each steps was completed before moving to the next, like razterize all pdf, resize all images, then process the OCR of all images, then all summaries. Now we want to work by tile items, for each item do resterize/resize, OCR, summary, json, then repeat with the next file. This way we can produce the PDF output in one shot and leave for the next module, the merger `md_mrg` will work only on the image items in the json batch file.

Note here we will only work on the `md_gen` module, leave the `md_mrg` untouched.

## Current status

The next modules in `md_gen` are mostly done:
- `config.py`
- `discovery.py`

We want to merge `rasterizer.py`/`resizer.py` module such that we pass the filepath and it return the PIL image object of the rie size. Internally it will discriminate between PDF and Images. With this we want to keep this module simple.

We want to update the `ocr_processor.py` to receive the image and give back the OCR text, no more than that. No file writings. This module will also return the summary of the page.

We want to combine the `markdown_write.py` and `metadata_writer.py` into a single module `page_processor.py` that apply the OCR process described in the previous section to a single file. It received the file, pdf or image` and follor the steps rasterize/resize, ocr, summary, markdown document, and in memory dict with metadata. The result of this module with markdown file in disk (single already merged pdf file or text of the single image page), and will return to the caller/invoker only the dict with the metadata.

The module `foundation.py` will keep its role as orchestator, however must be changes to the new workflow and work page by page. 

For every page we want to print to the console the status, something like: "Processing file [filename] ... done n pages", where filename is just the stem with extension, no need to print the full path.

In the output directory we will have all the markdown files (no resized images) and a single json with the batch item (the dict list with the metadata foe each file item), where each item appear in the same sorted discovery list.

## First steps

Start by inspecting the current mess and partially reworked modules in the folder `src/md_gen`. Some files will need to be deleted or merged into another, other will have to be writen from scratch. This is expected due to the hard change of workflow.

---

# Refinement Iteration 1
**Status:** PENDING USER FEEDBACK

## 1. Executive Summary
This issue refactors the `md_gen` module from a batch-stage workflow (rasterize all, OCR all, summarize all) to a per-item tile workflow where each discovered file is fully processed (rasterize/resize → OCR → page summary → markdown write → metadata capture) before moving to the next file. The `rasterizer.py` and `resizer.py` modules will be merged, `ocr_processor.py` will be simplified to pure image-in/text-out behavior, `markdown_writer.py` and `metadata_writer.py` will be combined into a new `page_processor.py`, and `foundation.py` will be restructured as the per-item orchestrator.

## 2. Refined Requirements & Acceptance Criteria

- **Requirement R1:** Configuration loading and CLI argument priority
  - **Description:** The CLI must build a configuration object where user-provided command-line arguments override values loaded from `data/config/settings.json`. If `settings.json` does not exist, it must be created from defaults first.
  - **Acceptance Criteria:**
    - [ ] Given `data/config/settings.json` is missing, when the CLI starts, then the file is created with default values before CLI arguments are applied.
    - [ ] Given a setting exists in both `settings.json` and a CLI argument, when the configuration is built, then the CLI argument value takes precedence.

- **Requirement R2:** Discovery of source files with natural sort ordering
  - **Description:** The discovery phase scans the mandatory `source` directory at a single level (no subdirectory traversal) for files with extensions `.pdf`, `.png`, `.jpg`, `.jpeg`. Files are ordered using natural (human) sort so that whole numbers are compared numerically (e.g., `file2.pdf` precedes `file10.pdf`).
  - **Acceptance Criteria:**
    - [ ] Given a source directory containing `file10.pdf` and `file2.pdf`, when discovery runs, then the resulting `FileItem` list is ordered `[file2.pdf, file10.pdf]`.
    - [ ] Given a source directory with subdirectories, when discovery runs, then files inside subdirectories are ignored.
    - [ ] Given a source directory with mixed-case extensions (e.g., `.PDF`, `.JPG`), when discovery runs, then the behavior is deterministic and documented.

- **Requirement R3:** Unified rasterize/resize module
  - **Description:** A single module (name to be confirmed) accepts a file path and returns a PIL image resized so that its longest edge does not exceed `max_edge_size`. The module internally discriminates between PDFs (rasterize page) and images (resize directly).
  - **Acceptance Criteria:**
    - [ ] Given a PDF file path and a page number, when the module is called, then it returns a PIL image of the requested page resized to the configured maximum edge.
    - [ ] Given an image file path, when the module is called, then it returns a resized PIL image with no rasterization step.
    - [ ] Given an unsupported file type, when the module is called, then it raises a clear, typed error.
    - **User: for PDF files will will need to first get the number of pages and pass a page argument, so this module returns a single image per call. However, for large files should we device some sort of caching for the PDF file? so what we are looking for is to be memory efficient. For image files, the page index can be ignore.**

- **Requirement R4:** OCR processor as pure image-to-text service
  - **Description:** `ocr_processor.py` receives a PIL image and returns the OCR-extracted markdown text. It performs no file I/O and no summary generation.
  - **Acceptance Criteria:**
    - [ ] Given a PIL image, when `ocr_processor` processes it, then it returns a string containing the OCR markdown text.
    - [ ] Given the same image, when processed twice, then the returned text is deterministic (when using deterministic model settings or mocks).

- **Requirement R5:** Page-level summary generation
  - **Description:** After OCR text is produced for a page, a language model generates a concise summary of that page's text. Page summaries are collected per file and then combined into a single document summary after the file's last page.
  - **Acceptance Criteria:**
    - [ ] Given a single-page PDF or image, when processing completes, then the document summary equals the single page summary.
    - [ ] Given a multi-page PDF, when all pages are processed, then a final summary is generated from the collected page summaries.
    - [ ] Given an empty OCR result, when summarization runs, then the behavior is deterministic and documented.

- **Requirement R6:** Per-file page processor
  - **Description:** A new `page_processor.py` module processes one file end-to-end: rasterize/resize each page, OCR, summarize, append markdown to a single per-file markdown document, and build an in-memory metadata dict. It writes the markdown file to disk and returns only the metadata dict.
  - **Acceptance Criteria:**
    - [ ] Given a PDF file, when `page_processor` runs, then one markdown file is written containing all page OCR text and a metadata dict is returned.
    - [ ] Given an image file, when `page_processor` runs, then one markdown file is written and a metadata dict is returned.
    - [ ] Given the returned metadata dict, when inspected, then it contains at minimum: discovery index, file type, file stem/extension or path, document summary, and output markdown file path.

- **Requirement R7:** Foundation orchestrator drives per-item workflow
  - **Description:** `foundation.py` iterates over the sorted `FileItem` list, invokes `page_processor` for each file, collects the returned metadata dicts, and writes the final batch JSON.
  - **Acceptance Criteria:**
    - [ ] Given a list of discovered files, when `foundation` runs, then each file is processed sequentially and completely before the next file starts.
    - [ ] Given all files are processed, when the run ends, then a single JSON file containing the list of metadata dicts is written to the output directory.
    - [ ] Given a file is being processed, when each page completes, then a console message is printed in the form `Processing file [filename] ... done n pages`.

- **Requirement R8:** Output directory contents
  - **Description:** The output directory contains one markdown file per discovered file and one JSON batch file describing the entire run. No intermediate resized images are written.
  - **Acceptance Criteria:**
    - [ ] Given a run with N input files, when processing completes, then the output directory contains exactly N markdown files and 1 JSON file.
    - [ ] Given the output directory after a run, when inspected, then no resized/rasterized image files are present.

- **Requirement R9:** Scope isolation
  - **Description:** Only `md_gen` is modified. `md_mrg` is left untouched.
  - **Acceptance Criteria:**
    - [ ] Given the refactor is complete, when `md_mrg` files are inspected, then no changes have been made to them.

## 3. Scope & Constraints

- **In-Scope:**
  - Refactoring `md_gen` to a per-item tile workflow.
  - Merging `rasterizer.py` and `resizer.py` into one module.
  - Simplifying `ocr_processor.py` to image-in/text-out.
  - Creating `page_processor.py` from `markdown_writer.py` and `metadata_writer.py`.
  - Rewriting `foundation.py` as the per-item orchestrator.
  - Updating or removing existing unit tests that cover the merged/deleted modules.
  - Writing console status messages per file.

- **Out-of-Scope:**
  - Any changes to `md_mrg` logic or interfaces.
  - Frontend or backend modules.
  - Cloud service integrations; local/offline behavior remains first-class.

- **Technical Constraints / Edge Cases:**
  - Discovery must not traverse subdirectories.
  - File ordering must use natural sort, not raw lexicographic sort.
  - OCR and summarization may use the same model gateway but must remain conceptually separate operations.
  - The merged rasterize/resize module must handle both PDF page indexing and image resizing uniformly.
  - Error handling for unreadable PDFs, corrupt images, or failed OCR/summary calls must be defined.

## 4. Open Design Choices (Questions for User)

- **[Technical]:** What should the merged rasterize/resize module be named? Suggested names: `image_prep.py`, `media_prep.py`, `rasterizer.py` (reused), or `preprocessor.py`.
**User: rasterizer.py**

- **[Technical]:** Where should page-level summarization live? The overview describes OCR returning a summary, but Requirement R4 isolates `ocr_processor.py` to image-to-text only. Should `page_processor.py` own both page summary and final document summary, or should a separate `summarizer.py` module be created?
**User: agree, we should have a `summarize.py` module.**

- **[Technical]:** What is the exact structure/schema of the `FileItem` and metadata dict (WorkItem)? Specifically, which fields are required, and should file paths be absolute or relative to the source/output directories?
**User: 
    - Source file name (full)
    - File type (pdf or image)
    - Page count (for images will be always 1)
    - Date of process
    - Summary
    - markdown file
At least this field. Other can be added if demmed necesary.**

- **[Technical]:** What are the naming conventions for output markdown files and the batch JSON file? For example, should the markdown file be `{source_stem}.md` and the JSON be `batch.json` or `{timestamp}_batch.json`?
**User: The md files have the same name as the source file, for instance, invoice-32.pdf will get a invoice-32.md. For the json `batch.json` is fine.**

- **[Business Logic]:** How should failures be handled per page or per file? Options: abort the entire batch, skip the failed file and continue, or write a partial markdown file with an error marker.
**User: print the error message, include a status in the metadata as failed, write the partial markdown so far, and move with the next file.**

- **[Technical]:** Should file extension matching be case-insensitive (accept `.PDF`, `.JPG`) or strictly lowercase? This affects discovery behavior.
**User: case insensitive.**

- **[Technical]:** Should the console status message print after each page (`done 1 pages`, `done 2 pages`, ...) or only once after the file is complete? The phrasing "done n pages" suggests a final count, but "for every page we want to print" suggests per-page progress.
**User: yes, print >    page 1 done\n>    page 2 done ...*

- **[Technical]:** Are existing tests for `rasterizer.py`, `resizer.py`, `markdown_writer.py`, and `metadata_writer.py` expected to be deleted, rewritten for the new modules, or preserved and updated?
**User: Due to the level of changes, the test for these module will be mostly invalid. The test can be rewriten and totally invalid one can be deleted.**

---

# Refinement Iteration 2
**Status:** LOCKED

## 1. Executive Summary
This issue refactors `md_gen` into a per-item tile workflow. Each discovered file is fully processed before moving to the next: `rasterizer.py` prepares one image at a time, `ocr_processor.py` extracts text, a new `summarize.py` module generates page and document summaries, `page_processor.py` orchestrates a single file end-to-end and writes its markdown, and `foundation.py` drives the whole batch and emits `batch.json`. All open design choices from Iteration 1 have been resolved.

## 2. Refined Requirements & Acceptance Criteria

- **Requirement R1:** Configuration loading and CLI argument priority
  - **Description:** The CLI must build a configuration object where user-provided command-line arguments override values loaded from `data/config/settings.json`. If `settings.json` does not exist, it must be created from defaults first.
  - **Acceptance Criteria:**
    - [ ] Given `data/config/settings.json` is missing, when the CLI starts, then the file is created with default values before CLI arguments are applied.
    - [ ] Given a setting exists in both `settings.json` and a CLI argument, when the configuration is built, then the CLI argument value takes precedence.

- **Requirement R2:** Discovery of source files with natural sort ordering
  - **Description:** The discovery phase scans the mandatory `source` directory at a single level (no subdirectory traversal) for files with extensions `.pdf`, `.png`, `.jpg`, `.jpeg` (case-insensitive). Files are ordered using natural (human) sort so that whole numbers are compared numerically (e.g., `file2.pdf` precedes `file10.pdf`).
  - **Acceptance Criteria:**
    - [ ] Given a source directory containing `file10.pdf` and `file2.pdf`, when discovery runs, then the resulting `FileItem` list is ordered `[file2.pdf, file10.pdf]`.
    - [ ] Given a source directory with subdirectories, when discovery runs, then files inside subdirectories are ignored.
    - [ ] Given a source directory with mixed-case extensions (e.g., `.PDF`, `.JPG`), when discovery runs, then the files are included.

- **Requirement R3:** Unified rasterize/resize module (`rasterizer.py`)
  - **Description:** `rasterizer.py` accepts a file path and returns a single PIL image per call, resized so that its longest edge does not exceed `max_edge_size`. For PDFs, the caller passes a page number and the module rasterizes only that page. For images, the page index is ignored and the image is resized directly. The module must be memory-efficient and not hold the entire PDF open unnecessarily.
  - **Acceptance Criteria:**
    - [ ] Given a PDF file path and a page number, when the module is called, then it returns a PIL image of the requested page resized to the configured maximum edge.
    - [ ] Given an image file path, when the module is called, then it returns a resized PIL image and the page index is ignored.
    - [ ] Given an unsupported file type, when the module is called, then it raises a clear, typed error.
    - [ ] Given a large multi-page PDF, when pages are requested one at a time, then memory usage remains bounded (no full-document caching required).

- **Requirement R4:** OCR processor as pure image-to-text service
  - **Description:** `ocr_processor.py` receives a PIL image and returns the OCR-extracted markdown text. It performs no file I/O and no summary generation.
  - **Acceptance Criteria:**
    - [ ] Given a PIL image, when `ocr_processor` processes it, then it returns a string containing the OCR markdown text.
    - [ ] Given the same image, when processed twice with deterministic settings or mocks, then the returned text is deterministic.

- **Requirement R5:** Summary generation in a dedicated `summarize.py` module
  - **Description:** A new `summarize.py` module generates a concise summary of a page's OCR text and, after a file's last page, combines all page summaries into a single document summary. If the file has only one page, the document summary equals the single page summary.
  - **Acceptance Criteria:**
    - [ ] Given a single-page PDF or image, when processing completes, then the document summary equals the single page summary.
    - [ ] Given a multi-page PDF, when all pages are processed, then a final summary is generated from the collected page summaries.
    - [ ] Given an empty OCR result, when summarization runs, then the behavior is deterministic and documented.

- **Requirement R6:** Per-file page processor (`page_processor.py`)
  - **Description:** `page_processor.py` processes one file end-to-end: for each page, call `rasterizer.py`, call `ocr_processor.py`, collect page summaries via `summarize.py`, append OCR text to a single per-file markdown document, and build an in-memory metadata dict. It writes the markdown file to disk and returns only the metadata dict.
  - **Acceptance Criteria:**
    - [ ] Given a PDF file, when `page_processor` runs, then one markdown file is written containing all page OCR text and a metadata dict is returned.
    - [ ] Given an image file, when `page_processor` runs, then one markdown file is written and a metadata dict is returned.
    - [ ] Given the returned metadata dict, when inspected, then it contains at minimum: source file name (full), file type, page count, date of process, document summary, output markdown file path, and status.

- **Requirement R7:** Foundation orchestrator drives per-item workflow
  - **Description:** `foundation.py` iterates over the sorted `FileItem` list, invokes `page_processor` for each file, collects the returned metadata dicts, and writes the final `batch.json`.
  - **Acceptance Criteria:**
    - [ ] Given a list of discovered files, when `foundation` runs, then each file is processed sequentially and completely before the next file starts.
    - [ ] Given all files are processed, when the run ends, then a single JSON file named `batch.json` containing the list of metadata dicts is written to the output directory.
    - [ ] Given a file is being processed, when each page completes, then a console message is printed in the form `page n done`.

- **Requirement R8:** Output directory contents and naming
  - **Description:** The output directory contains one markdown file per discovered file and one JSON batch file named `batch.json`. Markdown files use the same base name as the source file (e.g., `invoice-32.pdf` becomes `invoice-32.md`). No intermediate resized images are written.
  - **Acceptance Criteria:**
    - [ ] Given a run with N input files, when processing completes, then the output directory contains exactly N markdown files and 1 JSON file named `batch.json`.
    - [ ] Given a source file `invoice-32.pdf`, when processed, then the output markdown file is named `invoice-32.md`.
    - [ ] Given the output directory after a run, when inspected, then no resized/rasterized image files are present.

- **Requirement R9:** Failure handling per file
  - **Description:** If a file fails during processing (unreadable PDF, corrupt image, failed OCR/summary, etc.), the error is printed to the console, the metadata dict is marked with a failed status, any partial markdown produced so far is written, and processing continues with the next file.
  - **Acceptance Criteria:**
    - [ ] Given a corrupt file in the source directory, when the batch runs, then an error message is printed and the file's metadata status is `failed`.
    - [ ] Given a failed file, when processing continues, then the next file in the discovery list is processed.
    - [ ] Given a failed file produced partial markdown, when the run ends, then the partial markdown file is present in the output directory.

- **Requirement R10:** Scope isolation
  - **Description:** Only `md_gen` is modified. `md_mrg` is left untouched.
  - **Acceptance Criteria:**
    - [ ] Given the refactor is complete, when `md_mrg` files are inspected, then no changes have been made to them.

- **Requirement R11:** Test updates
  - **Description:** Existing tests for merged, deleted, or heavily changed modules are rewritten or removed as needed to match the new architecture.
  - **Acceptance Criteria:**
    - [ ] Given the refactor is complete, when tests are run, then they reflect the new `rasterizer.py`, `ocr_processor.py`, `summarize.py`, `page_processor.py`, and `foundation.py` interfaces.
    - [ ] Given a test covers a removed module or behavior, when the test suite is reviewed, then the test is removed or replaced.

## 3. Scope & Constraints

- **In-Scope:**
  - Refactoring `md_gen` to a per-item tile workflow.
  - Merging `rasterizer.py` and `resizer.py` into `rasterizer.py`.
  - Simplifying `ocr_processor.py` to image-in/text-out.
  - Creating a new `summarize.py` module for page and document summaries.
  - Creating `page_processor.py` from `markdown_writer.py` and `metadata_writer.py`.
  - Rewriting `foundation.py` as the per-item orchestrator.
  - Updating or removing existing unit tests that cover the merged/deleted modules.
  - Writing per-page console status messages.
  - Per-file failure handling with failed status and partial markdown output.

- **Out-of-Scope:**
  - Any changes to `md_mrg` logic or interfaces.
  - Frontend or backend modules.
  - Cloud service integrations; local/offline behavior remains first-class.

- **Technical Constraints / Edge Cases:**
  - Discovery must not traverse subdirectories.
  - File extension matching is case-insensitive.
  - File ordering must use natural sort, not raw lexicographic sort.
  - OCR and summarization use separate modules; `ocr_processor.py` performs no summarization.
  - `rasterizer.py` returns one image per call and must be memory-efficient for large PDFs.
  - Output markdown files share the source file base name; batch JSON is always `batch.json`.
  - Metadata dict must include: source file name, file type, page count, date of process, summary, output markdown file path, and status.
  - Failures are handled per file: print error, mark status as failed, write partial markdown, continue with next file.

**User: note that `config.py` and `discovery.py` are mostly done, these will require the least changes if any.**

**LOCKED**


