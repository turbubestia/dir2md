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

## Coding and Style Conventions
- Keep modules small and testable; favor pure functions for transformations.
- Use typed Python signatures for public interfaces.

## Environment and Execution
- Use `uv` managed virtual environments for dependency and command execution.
- Ensure local runs/tests are executed in the project environment.
- Do not assume cloud services; local/offline behavior is first-class.

## Testing Guidance
- Prefer fast unit tests for token sizing, path planning, and grouping heuristics.
- Add integration tests for end-to-end CLI flows with fixture PDFs/images.
- Mock model responses for deterministic tests.
- pytest is setup and ready to use for running both unit and integration tests with code coverage support.
- Ensure tests are run within the project environment to maintain consistency with local development.
- Use `pytest` command with appropriate flags to check code coverage and test results.

