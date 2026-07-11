# Issue 5 - Use on LLM for Bridge Score

Current implementation has few options to set the input and output for the md_gen module and a few the options for page bridge score. We want to make updates to this two features.

## MD_GEN Goals

The current input file discovery is kind of a mess accepting multiple source files and directories, and can specify different temp folders and the output is not required. We want to change this behavior as follow:
- Accept a single source folder to scan for PDF and images. The scan is single level, do not traverse through sub-folders.
- Only accept folders, not single files as arguments
- Only accept one source folder and one output folder, both must be mandatory
- Produce a single `temp` folder at the output to place intermeadiary files like the small images, json metadata, and md files.
- The test files of the md_gen modules must be placed in `test/md_gen`. Currently they are all bunch tigether in `test` coliding with the other modules.
- The prompt to ask for the summary must come from a file so we can test different prompts.
- The CLI should now accept the source and output command, and not commands for the temp folders. The temp folder will be `output/temp`
    - the arguments `md-temp-dir` and `mg-temp-dir` are no longer required

## MD_MRG Goals

The current bridge strategy to merge single image pages allow to choose an heuristic method and a LLM one. I try both and only the LLM produce the desired effect. We want to get the next features
- The prompt for the LLM to get the score must come from a file, so we can test different prompts.
- Keep in place the scorer interface but remove completely the heuristim one.
- Keep the CLI command edge-scorer only with the `llm` option by default.
- There should be only one source folder option (which would be the output folder of md_gen), from here we will discover the sources md and json from the `output/temp`
    - the planer will look at `output/temp` and will produce the jsom batch at `output`
    - the apply will get the json from `output`
    - the arguments `md-temp-dir` and `mg-temp-dir` are no longer required
- Test must be place at `test/md_mrg`.

## Global Goals

- Fix current test and add new ones as required to test as much as possible.
- Add code coverage test when possible (we will need to add the requirement to pyproject.toml)

## Requirement Analysis (Appended, No Original Content Removed)

This section translates the draft into explicit, testable requirements and highlights decisions still needed.

### 1) Clarified Functional Requirements

#### 1.1 MD_GEN Input/Output Contract

- CLI must accept named flags `--source` and `--output`.
- CLI must accept exactly one source directory and exactly one output directory.
- Both source and output are mandatory arguments.
- Source must be a directory; file-path inputs are invalid.
- Source scan must be non-recursive (single level only).
- Discovery scope is PDFs and image files with these extensions only: `.png`, `.jpg`, `.jpge`.
- Unsupported files must be skipped.
- During discovery, console output must report discovered files and whether each file was consumed or skipped.
- Output directory must be created automatically if it does not exist.
- Temp layout must be unified under one folder: `output/temp`.
- Intermediate artifacts now live under `output/temp` (resized images, JSON metadata, markdown files).
- Existing files under `output/temp` are kept (no automatic cleanup) for debugging.
- Legacy temp CLI arguments are removed:
    - `md-temp-dir`
    - `mg-temp-dir`

#### 1.2 MD_GEN Prompt Externalization

- LLM summary prompt must be loaded from a file instead of being hardcoded.
- Default prompt file must exist in-repo.
- Prompt file can be overridden with `--summary-prompt`.
- Prompt format is plain text only and corresponds to the text used for `system_prompt` in request payload construction.
- If prompt file is missing/unreadable, fallback to built-in default prompt text.

#### 1.3 MD_MRG Scoring Strategy Simplification

- Keep scorer abstraction/interface in code.
- Remove heuristic scorer implementation and its usage paths.
- Keep LLM scorer as the only active scorer behavior.
- CLI `edge-scorer` option remains but supports only `llm` as the effective/default value.

#### 1.4 MD_MRG Input/Output Contract

- MD_MRG must use named flag `--source` only.
- MD_MRG should accept a single source directory (expected to be MD_GEN output directory).
- MD_MRG planner reads markdown/metadata inputs from `source/temp`.
- MD_MRG planner writes deterministic merge plan batch JSON to `source` (source root dir, not temp).
- MD_MRG apply step reads plan JSON from `source`.
- Planner/apply remain separate commands.
- Default score prompt file must exist in-repo.
- Score prompt file can be overridden with `--score-prompt`.
- If score prompt file is missing/unreadable, fallback to built-in default prompt text.
- Legacy temp CLI arguments are removed:
    - `md-temp-dir`
    - `mg-temp-dir`

#### 1.5 Test Structure and Quality

- Tests should be reorganized by module:
    - MD_GEN tests in `test/md_gen`
    - MD_MRG tests in `test/md_mrg`
- Existing tests must be fixed after behavior/CLI contract changes.
- New tests should be added for the new contracts and error cases.

#### 1.6 Coverage

- Add coverage tooling/dependency in `pyproject.toml`.
- Add a documented way to run tests with coverage.
- Establish an initial minimum coverage target of 60%.
- Coverage reporting should be per module (`md_gen` and `md_mrg`).

#### 1.7 Errors and Logging

- Errors must include machine-readable codes and human-readable messages.
- Console output is required.
- File logging is no longer required and should be removed.

#### 1.8 Backward Compatibility

- No backward compatibility period is required.
- Legacy arguments and obsolete code paths should be removed immediately.

### 2) Inferred Acceptance Criteria

#### 2.1 MD_GEN

- Command fails with clear validation error if source is missing, output is missing, or source is a file.
- Command uses `--source` and `--output` as required named flags.
- Command ignores nested subfolders during source discovery.
- Command only consumes `.png`, `.jpg`, `.jpge`, and supported PDFs.
- Command prints discovery decisions (consumed/skipped) to console.
- On run, temp artifacts are created only under `output/temp`.
- Output directory is created automatically when missing.
- Existing temp contents are preserved unless user manually removes them.
- No behavior depends on `md-temp-dir` or `mg-temp-dir`.
- Summary prompt defaults to in-repo file, can be overridden with `--summary-prompt`, and falls back to built-in default when file is unavailable.

#### 2.2 MD_MRG

- Planner/apply flow remains split across two commands.
- Commands use only `--source` named flag.
- Planner reads inputs from `source/temp` and writes plan JSON into `source`.
- Apply reads plan JSON from `source`.
- Planner output JSON naming is deterministic.
- Heuristic scorer cannot be selected or executed.
- `edge-scorer` resolves to LLM-only behavior.
- Score prompt defaults to in-repo file, can be overridden with `--score-prompt`, and falls back to built-in default when file is unavailable.

#### 2.3 Tests and Coverage

- Test suite passes after test relocation and updates.
- New tests cover required validation, path resolution, prompt-file loading/fallback, and LLM-only scorer behavior.
- Coverage command runs successfully and reports per-module coverage metrics.
- Minimum coverage threshold enforces at least 60%.

### 3) Scope and Impact Notes

- This change is a contract simplification and will break old CLI usage that relied on multiple source args and custom temp dirs.
- No backward compatibility shim is required.
- Migration notes/changelog updates are likely needed to avoid user confusion.
- Prompt-file loading introduces new runtime failure paths (missing file, unreadable file, empty content, invalid template variables).
- Fallback behavior to built-in prompt defaults reduces runtime hard-fail risk for prompt file issues.
- Existing file-log-oriented behavior should be removed in favor of console-only output.

### 4) Open Design Questions (Need Your Answers)

1. MD_GEN CLI shape: Should the two required path arguments be positional (`md-gen <source_dir> <output_dir>`) or named flags (`--source-dir`, `--output-dir`)?
**User: named flags `--source` and `--output`.**

2. Source discovery extensions: Which exact image extensions are allowed (for example: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.webp`, `.bmp`)?
**User: accept `.png`, `.jpg`, `.jpge`.**

3. Discovery behavior for unsupported files: Should unsupported files be silently skipped or reported in logs/summary?
**User: unsuported files should be skip. During the discovery phase print to the console the discovered files and is were consumed or skipped.**

4. Output folder existence policy: Should output be auto-created if missing, or fail unless it already exists?
**User: should be created is missing.**

5. Temp folder cleanup policy: Should `output/temp` be reused, overwritten, or require a `--force` behavior when files exist?
**User: keep the folder in place for debug reasons. Let the user delete it afterward.**

6. Prompt file location (MD_GEN): Do you want a default prompt file path in-repo plus optional CLI override, or required explicit prompt path every run?
**User: default file prompt in repo with optional flag --summary-prompt to specify the file.**

7. Prompt file location (MD_MRG): Same policy as MD_GEN, or separate defaults/flags?
**User: default file prompt in repo with optional flag --score-prompt to specify the file.**

8. Prompt format: Plain text with token placeholders, Jinja-like templating, or strict static prompt text only?
**User: It will only have plain text, it is actually the text place in the `system_prompt` variable (see `build_text_summary_request_payload`).**

9. Missing prompt file behavior: Hard fail immediately, or fallback to built-in default prompt text?
**User: use built-in default.**

10. `edge-scorer` UX: Keep the argument visible but constrained to `llm`, or fully remove the option and always use LLM implicitly?
**User: keep the argument but constrain to `llm` only.**

11. Planner/apply command boundaries: Do you want one combined command mode, or keep separate planner/apply commands with the new path conventions?
**User: keep current behavior, two separated paths.**

12. Plan JSON naming: Should output JSON filename be deterministic fixed name, timestamped, or user-provided?
**User: deterministic.**

13. MD_MRG source argument naming: Should it be called `--output-dir` (to mirror MD_GEN output) or `--source-dir` (because it is MD_MRG input)?
**User: We only need the `--source source_folder` flag since the temp files will be at `source_folder/temp`, the batch json will be produce at `source_folder` and the merged document also will be place at `source_folder`, so we don't realy need a --output flag.**

14. Error messaging standard: Do you want standardized machine-readable errors (codes) or human-readable text only?
**User: machine codes with human-readable text. We won't need a log file, just console output. So log to file can be drop.**

15. Test migration strategy: Move existing tests as-is first, then refactor names/fixtures, or refactor while moving?
**User: yes, move first the fix them.**

16. Coverage target: Do you want a minimum gate (for example 80%/85%/90%) enforced in CI/test command?
**User: We want to start at least 60% coverage. we can increase it later.**

17. Coverage scope: Should coverage include both modules together or separate per-module reports (`md_gen` and `md_mrg`)?
**User: per module test and coverage.**

18. Backward compatibility window: Do you want a temporary deprecation period for old args, or immediate removal?
**User: we don't need backward compatibility. Remove any old code to keep it clean. This software has not been publish so there is no public contract.**

### 5) Proposed Requirement Tightening (After Questions Are Answered)

After your answers, this draft can be converted into:

- Final CLI contracts for MD_GEN and MD_MRG.
- Canonical folder/file layout specification.
- Prompt loading specification (path, format, fallback behavior).
- Deterministic planner/apply I/O contract.
- Test matrix and coverage policy with pass/fail thresholds.

## Finalized Requirement Baseline (From Answered Questions)

This section is the execution baseline for implementation.

### A) Final CLI Contract

- MD_GEN uses required named flags: `--source`, `--output`.
- MD_MRG uses required named flag: `--source`.
- Legacy `md-temp-dir` and `mg-temp-dir` arguments are removed.
- `edge-scorer` remains exposed but only accepts `llm`.

### B) Final Discovery and Path Rules

- Discovery is single-level only (no recursive traversal).
- Allowed image extensions are `.png`, `.jpg`, `.jpge`.
- Unsupported files are skipped.
- Discovery emits console output showing each discovered file and consumed/skipped outcome.
- Output directory is auto-created when missing.
- Intermediate artifacts are always under `output/temp`.
- Existing `output/temp` content is preserved for debugging (no automatic cleanup).

### C) Final Prompt Rules

- MD_GEN summary prompt:
    - Default in-repo prompt file.
    - Optional override flag: `--summary-prompt`.
    - Fallback to built-in default prompt when file is missing/unreadable.
- MD_MRG score prompt:
    - Default in-repo prompt file.
    - Optional override flag: `--score-prompt`.
    - Fallback to built-in default prompt when file is missing/unreadable.
- Prompt content format is plain text and maps to `system_prompt` content.

### D) Final Planner/Apply Behavior

- Planner and apply remain separate command paths.
- Planner reads from `source/temp` and writes deterministic JSON batch output in `source`.
- Apply reads plan JSON from `source`.

### E) Final Error and Logging Rules

- Errors must include machine-readable code + human-readable text.
- Console output is authoritative.
- Log-file output is removed.

### F) Final Test and Coverage Rules

- Move tests first, then fix/refactor.
- Module test layout:
    - `test/md_gen`
    - `test/md_mrg`
- Coverage is measured per module.
- Initial minimum coverage target is 60%.

### G) Compatibility Policy

- Immediate cleanup approach: remove old behavior and old arguments now.
- No deprecation window required.