# Copilot Onboarding Instructions for dir2md

## Project Purpose
- Build a local-first Python system that converts PDFs and images into Markdown with OCR.
- Normalize generated Markdown into final document groups with proposed filenames.
- Expose the workflow later through a Python backend and a frontend UI.

## Delivery Workflow
- Work goal-by-goal from the design request in `design/initial.request.md`.
- For each goal:
  1. Provide architecture analysis (no code).
  2. Provide implementation plan (no code).
  3. Implement.
- Stop after each requested design file so it can be reviewed before continuing.

## Module Boundaries
- `src/md-gen`: OCR ingestion CLI.
- `src/md-norm`: Markdown normalization and document consolidation CLI.
- `src/backend`: Python web backend.
- `src/frontend`: Web frontend.

Keep responsibilities separated. Do not duplicate OCR or normalization logic between modules.

## Core Behavioral Requirements
- `md-gen`:
  - Accept directory input and single/list file input (PDF/images).
  - Convert PDF pages to images.
  - Resize all images to model limits (max longest edge 1540 for LightOnOCR-2).
  - Write intermediate images to `im-temp`.
  - Write OCR markdown to `md-temp`.
  - Add metadata header containing source and page provenance.

- `md-norm`:
  - Read markdown from `md-temp`.
  - Summarize page content for grouping decisions.
  - Detect pages belonging to same logical document.
  - Propose normalized filenames using configurable naming format.
  - Plan merge operations (image-to-pdf and markdown consolidation).

## AI Model Integration Requirements
- OCR model: LightOnOCR-2 served locally via llama.cpp.
- Normalization model: Gemma-4-E4B (or configured Gemma variant) served locally via llama.cpp.
- llama.cpp will be running provided by the user, do not assume cloud access, and do not implement model serving in this project.
- Keep model access behind adapter interfaces so runtime backends can be swapped without touching business logic.

## Coding and Style Conventions
- Use Python snake_case for variables, functions, methods, and classes.
- Keep modules small and testable; favor pure functions for transformations.
- Use typed Python signatures for public interfaces.
- Keep side effects at orchestration boundaries (CLI entrypoints, backend handlers, file IO adapters).

## Environment and Execution
- Use `uv` managed virtual environments for dependency and command execution.
- Ensure local runs/tests are executed in the project environment.
- Do not assume cloud services; local/offline behavior is first-class.

## Data and File Safety
- Never delete source files during dry-run or analysis phases.
- Explicitly separate temp outputs from final outputs.
- Keep idempotent operations where possible (reruns should not corrupt results).

## Testing Guidance
- Prefer fast unit tests for token sizing, path planning, and grouping heuristics.
- Add integration tests for end-to-end CLI flows with fixture PDFs/images.
- Mock model responses for deterministic tests.

## Documentation Expectations
- For each goal, create design docs under `design/` before implementation.
- Document assumptions, constraints, and unresolved decisions explicitly.

## Commit Message Template
Use a structured commit format based on Conventional Commits.

Template:

```text
<type>(<optional-scope>): <short imperative summary>

<optional body>

<optional footer(s)>
```

Recommended `type` values:
- `feat`: new user-facing behavior
- `fix`: bug fix or behavior correction
- `refactor`: code change without behavior change
- `perf`: performance improvement
- `test`: tests added or updated
- `docs`: documentation-only change
- `build`: build or dependency changes
- `ci`: CI/CD pipeline changes
- `chore`: maintenance tasks

Formatting rules:
- Keep the subject line concise (prefer <= 72 chars)
- Use imperative mood (e.g., "add", "fix", "refactor")
- Do not end the subject with a period
- In the body, explain what changed and why
- Wrap body lines for readability (prefer around 72 chars)
- Use footer for references (e.g., `Refs: #123`) and breaking changes

Breaking changes:
- Add `!` after type/scope, or include `BREAKING CHANGE:` in footer

Examples:

```text
feat(md-gen): add markdown provenance persistence for OCR outputs

Write OCR results to md-temp with deterministic filenames and
front-matter metadata for downstream normalization.

Refs: #42
```

```text
fix(md-gen)!: require overwrite for existing markdown outputs

Prevent silent replacement by failing when target markdown already
exists unless --overwrite is explicitly provided.

BREAKING CHANGE: reruns now require --overwrite to replace md-temp files.
```
