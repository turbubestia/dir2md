# Issue 15 Sub-Issue 2

for debug purposes I want to add a `--verbose` argument such that all the configuration is printed (nicely) before running the `run_foundation_bootstrap ` function. This include print the actual summary prompt to know what exactly we are sending to the language LLM. Add a separate config_dump.py module for this requirement.

# Refinement Iteration 1
**Status:** PENDING USER FEEDBACK

## 1. Executive Summary
Add a debug-oriented `--verbose` CLI flag to `md_gen` so the fully resolved runtime configuration can be inspected before the batch pipeline starts. The new behavior should print a readable configuration dump, including the effective summary prompt text that will be sent to the language model, and should centralize formatting in a new `config_dump.py` module.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement R1: Add verbose CLI flag**
	- **Description:** Extend `src/md_gen/cli.py` to accept a `--verbose` boolean flag that controls whether the resolved configuration is emitted before `run_foundation_bootstrap` is called.
	- **Acceptance Criteria:**
		- [ ] Given `md-gen` is invoked with `--verbose`, when argument parsing succeeds, then the program emits a configuration dump before entering the batch bootstrap path.
		- [ ] Given `md-gen` is invoked without `--verbose`, when argument parsing succeeds, then no configuration dump is emitted and existing startup behavior remains unchanged.

- **Requirement R2: Provide a dedicated config dump module**
	- **Description:** Add a new `src/md_gen/config_dump.py` module responsible for rendering the resolved `AppConfig` in a readable, structured format.
	- **Acceptance Criteria:**
		- [ ] Given a resolved `AppConfig`, when the dump helper is called, then it returns or prints a human-readable representation without requiring the caller to know formatting details.
		- [ ] Given future changes to config structure, when formatting logic changes, then the CLI entrypoint remains thin and delegates dump rendering to the new module.

- **Requirement R3: Show the effective summary prompt text**
	- **Description:** The configuration dump must include the actual summary prompt content that will be supplied to the language-model summarization step, not only the file path or source selector.
	- **Acceptance Criteria:**
		- [ ] Given the summary prompt comes from a custom file, default config, or built-in fallback, when verbose output is generated, then the displayed prompt text matches the effective text stored in `AppConfig`.
		- [ ] Given a configuration dump is produced, when a developer inspects it, then they can see which prompt text will be sent to the LLM before execution starts.

## 3. Scope & Constraints
- **In-Scope:**
	- Add a `--verbose` flag to the `md_gen` CLI.
	- Add a new `config_dump.py` module for formatting configuration output.
	- Include the resolved prompt text in the dump.
	- Emit the dump before `run_foundation_bootstrap` begins processing work items.
- **Out-of-Scope:**
	- Changing OCR, summarization, discovery, or batch-processing behavior.
	- Altering the effective configuration values themselves.
	- Adding new persistence or logging infrastructure beyond the startup dump.
- **Technical Constraints / Edge Cases:**
	- The dump must reflect the fully resolved configuration after CLI overrides, JSON settings, defaults, and prompt-file resolution have been applied.
	- The output should stay readable even when the summary prompt text is multi-line.
	- The implementation should preserve the current exit-code behavior for valid and invalid startup paths.

## 4. Open Design Choices (Questions for User)
- **[UX/UI]:** Should the verbose dump be written to standard output or standard error?
**User: standard output.**

- **[Technical]:** Should the dump include every config field verbatim, or should any values be redacted or summarized for readability?
**User: verbatim.**

- **[Technical]:** Do you want `--verbose` to only print the configuration once at startup, or should it also enable additional runtime diagnostics during processing?
**User: only the configuration at startup.**

# Refinement Iteration 2
**Status:** LOCKED

## 1. Executive Summary
The verbose configuration-dump requirement is now fully specified. The CLI will emit a single startup-only dump to standard output, rendered by a dedicated `config_dump.py` module, and the dump will include the complete resolved configuration plus the exact summary prompt text used for LLM calls.

## 2. Refined Requirements & Acceptance Criteria
- **Requirement R1: Emit startup-only verbose config dump**
	- **Description:** `src/md_gen/cli.py` must accept `--verbose` and, when provided, print the resolved configuration once to standard output before invoking `run_foundation_bootstrap`.
	- **Acceptance Criteria:**
		- [ ] Given `md-gen` is invoked with `--verbose`, when configuration resolution succeeds, then a single configuration dump is written before batch processing begins.
		- [ ] Given `md-gen` is invoked without `--verbose`, when configuration resolution succeeds, then no configuration dump is written and the existing execution flow is preserved.

- **Requirement R2: Centralize formatting in `config_dump.py`**
	- **Description:** Add `src/md_gen/config_dump.py` to own all formatting and presentation logic for the verbose dump so the CLI remains a thin orchestration layer.
	- **Acceptance Criteria:**
		- [ ] Given a resolved `AppConfig`, when the dump module formats it, then the output is human-readable and structured without requiring formatting logic in `cli.py`.
		- [ ] Given future config fields are added, when the dump module is updated, then the CLI call site does not need formatting changes.

- **Requirement R3: Print full configuration verbatim, including effective prompt text**
	- **Description:** The dump must include every resolved configuration value verbatim, including the actual summary prompt text stored in `AppConfig.prompts.summary_prompt_text`.
	- **Acceptance Criteria:**
		- [ ] Given the summary prompt is loaded from a custom file, JSON config, or built-in fallback, when `--verbose` is used, then the dump shows the exact effective prompt text that will be sent to the language model.
		- [ ] Given a developer reviews the verbose dump, when configuration fields are displayed, then no fields are redacted or summarized.
		- [ ] Given verbose mode is enabled, when the dump is emitted, then it is written to standard output only and does not enable additional runtime diagnostics beyond the startup dump.

## 3. Scope & Constraints
- **In-Scope:**
	- Add the `--verbose` CLI flag.
	- Add `config_dump.py` for startup configuration rendering.
	- Print the full resolved config and prompt text verbatim to standard output.
	- Keep the behavior limited to a single startup dump.
- **Out-of-Scope:**
	- Changing any configuration resolution rules.
	- Adding runtime debug logging during OCR, summarization, or file processing.
	- Redacting or masking configuration values.
- **Technical Constraints / Edge Cases:**
	- The dump must reflect the fully resolved configuration after defaults, JSON settings, CLI overrides, and prompt-file resolution.
	- Multi-line prompt text must remain readable in the output.
	- The verbose path must not change the exit-code behavior of valid or invalid startup flows.

**LOCKED**