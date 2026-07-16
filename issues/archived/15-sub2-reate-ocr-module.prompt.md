# Implementation Plan: 15-sub2-reate-ocr-module

> **Core Objective:** Add a verbose startup config dump for `md-gen` by introducing a dedicated formatter module, wiring it into CLI startup before bootstrap, and covering both the rendered output and CLI behavior with focused tests.

> **Metadata**
> - **Analysis Reference:** [15-sub2-reate-ocr-module.plan.analysis.md](./15-sub2-reate-ocr-module.plan.analysis.md)
> - **Primary Scope:** `src/md_gen/cli.py`, `src/md_gen/config_dump.py`, `test/md_gen/test_cli.py`, `test/md_gen/test_config_dump.py`
> - **Traceability Rule:** Every phase and step below implements requirements from Analysis Sections 1 through 4.

---

## Phase 1: Create the Config Dump Formatter

### Step 1.1: Add a dedicated presentation module for resolved startup config
- **Implements Analysis Section 1 and Section 2 (`src/md_gen/config_dump.py`).**
- **Target File:** `./src/md_gen/config_dump.py`
- **Action:** Create a small formatter module that accepts a fully resolved `AppConfig` and returns one human-readable startup dump string.
- **Implementation Shape:**
  - Add one public entry point such as `format_config_dump(config: AppConfig) -> str`.
  - Keep the module presentation-only: no config resolution, no bootstrap, no file I/O, no CLI parsing.
  - Render the resolved values for paths, prompts, OCR model, language model, image settings, and runtime settings in a stable labeled layout.
  - Emit `config.prompts.summary_prompt_text` verbatim, preserving line breaks exactly as stored in `AppConfig`.
  - Prefer a deterministic text layout that is easy to scan in terminal output and easy to assert in tests.
- **Exit Criterion:** The module can format an `AppConfig` instance into a single string that includes all requested sections and the exact multi-line summary prompt text.
- **Validation Command:** `uv run pytest test/md_gen/test_config_dump.py -v`

### Step 1.2: Define the dump output contract around existing AppConfig fields
- **Implements Analysis Section 3 (`Prompt Fidelity`, `Output Semantics`).**
- **Target File:** `./src/md_gen/config_dump.py`
- **Action:** Make the formatter reflect only already-resolved values from `AppConfig`; do not recompute defaults or re-read files.
- **Implementation Shape:**
  - Use the existing dataclass field names from `src/md_gen/config.py` as the source of truth.
  - Keep prompt text readable even when it spans multiple lines by preserving the raw text block rather than collapsing whitespace.
  - Ensure the output makes it obvious that the dump is diagnostic startup metadata, not pipeline progress.
- **Exit Criterion:** The formatter output can be inspected as a faithful snapshot of the resolved runtime config without any extra computation.
- **Validation Command:** `uv run pytest test/md_gen/test_config_dump.py -v`

## Phase 2: Wire Verbose Dumping Into CLI Startup

### Step 2.1: Add a `--verbose` flag to the parser
- **Implements Analysis Section 2 (`src/md_gen/cli.py`) and Section 4 (`Verify md-gen --verbose`).**
- **Target File:** `./src/md_gen/cli.py`
- **Action:** Extend `build_parser()` with a boolean `--verbose` flag that defaults to `False`.
- **Implementation Shape:**
  - Keep the parser change minimal and aligned with the existing `argparse` style in the file.
  - Do not change required arguments or existing startup options.
- **Exit Criterion:** `build_parser()` accepts `--verbose`, and parsed args expose a truthy `verbose` attribute only when the flag is present.
- **Validation Command:** `uv run pytest test/md_gen/test_cli.py -v`

### Step 2.2: Call the formatter before bootstrap when verbose mode is enabled
- **Implements Analysis Section 1 (`Data Flow Changes`) and Section 2 (`Logic Modifications Required`).**
- **Target File:** `./src/md_gen/cli.py`
- **Action:** After `build_config_from_args(simple_args)` succeeds, conditionally print the formatted config dump before invoking `run_foundation_bootstrap(config)`.
- **Implementation Shape:**
  - Import the new formatter module from `src/md_gen/config_dump.py`.
  - Keep `main()` as the orchestration layer: parse args, build config, optionally dump config, then call bootstrap.
  - Preserve the existing exception handling so `ConfigValidationError` and other startup failures still return the same exit codes.
  - Ensure the dump path is strictly gated on `args.verbose` and never runs when the flag is absent.
- **Exit Criterion:** In verbose mode, the config dump is emitted once and appears before any bootstrap stage output; in non-verbose mode, the startup flow remains unchanged.
- **Validation Command:** `uv run pytest test/md_gen/test_cli.py -v`

### Step 2.3: Keep the bootstrap path untouched aside from the new pre-step
- **Implements Analysis Section 1 (`Behavioral Boundary`) and Section 3 (`Error Handling`).**
- **Target File:** `./src/md_gen/cli.py`
- **Action:** Verify the new verbose branch does not alter config resolution, discovery, OCR, summarization, or error handling behavior.
- **Implementation Shape:**
  - Leave `run_foundation_bootstrap(config)` responsible for the existing pipeline behavior and exit codes.
  - Do not add formatting logic to `foundation.py`.
- **Exit Criterion:** Non-verbose invocations still return the same code paths and operational behavior as before this change.
- **Validation Command:** `uv run pytest test/md_gen/test_cli.py -v`

## Phase 3: Add Focused Tests for the New Behavior

### Step 3.1: Add unit tests for the formatter module
- **Implements Analysis Section 2 (`test/md_gen/test_config_dump.py`) and Section 4 (`Verify the dump includes...`).**
- **Target File:** `./test/md_gen/test_config_dump.py`
- **Action:** Create a focused test file that builds a representative `AppConfig` and asserts the rendered dump contains every required section plus the exact prompt text.
- **Implementation Shape:**
  - Include at least one multi-line prompt fixture so the test proves line breaks are preserved.
  - Assert the formatter output includes paths, prompts, OCR model, language model, image settings, and runtime settings.
  - Keep assertions strict enough to catch accidental prompt normalization or missing fields.
- **Exit Criterion:** The formatter is independently covered without going through the CLI entry point.
- **Validation Command:** `uv run pytest test/md_gen/test_config_dump.py -v`

### Step 3.2: Extend CLI tests for verbose and non-verbose startup paths
- **Implements Analysis Section 2 (`test/md_gen/test_cli.py`) and Section 4 (`Verify md-gen --verbose`).**
- **Target File:** `./test/md_gen/test_cli.py`
- **Action:** Update CLI tests to cover parser acceptance, config dump invocation order, and unchanged non-verbose behavior.
- **Implementation Shape:**
  - Add a parser assertion that `--verbose` is accepted.
  - Add a verbose-path test that patches the formatter and bootstrap call, then asserts the dump happens before bootstrap proceeds.
  - Add or adapt a non-verbose-path test to confirm the formatter is not called when the flag is absent.
  - Keep existing bootstrap assertions intact so output creation behavior is still covered.
- **Exit Criterion:** CLI tests prove the new flag is honored, the dump is gated correctly, and the original startup flow remains intact when verbose mode is off.
- **Validation Command:** `uv run pytest test/md_gen/test_cli.py -v`

## Phase 4: Final Verification

### Step 4.1: Run the targeted md_gen test slice
- **Implements Analysis Section 4 (all verification bullets).**
- **Target Command:** `uv run pytest test/md_gen -v`
- **Action:** Run the md_gen test subset to confirm the formatter unit tests and CLI integration tests pass together.
- **Exit Criterion:** The full `test/md_gen` slice passes with no regressions in parser behavior, verbose output ordering, or existing startup behavior.
- **Validation Command:** `uv run pytest test/md_gen -v`
