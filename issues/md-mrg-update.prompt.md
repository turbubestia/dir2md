> **Traceability Metadata**
> - [Analysis Reference](./md-mrg-update.plan.analysis.md)
> - Plan Scope: md-mrg-update

# Implementation Plan: md-mrg-update

> **Core Objective:** Detailed step-by-step technical execution blueprint for implementing the requirements specified in the analysis.

## Phase 1: Baseline Contract And File Skeleton

Implementing requirements from Analysis Section 1 (pipeline/data flow), Analysis Section 2 (new files in `src/md_mrg`), and Analysis Section 4 (CLI and file-contract checklist items).

### Steps
- Create runtime module skeletons:
  - `src/md_mrg/cli.py`
  - `src/md_mrg/planner.py`
  - `src/md_mrg/apply.py`
  - Update `src/md_mrg/__init__.py` exports to remain side-effect free.
- Define shared constants in md_mrg modules (deterministic filenames, score threshold, batch file names):
  - `BATCH_FILE_NAME = "batch.json"`
  - `MRG_PLAN_FILE_NAME = "batch_mrg.json"`
  - `MRG_RESULT_FILE_NAME = "batch_mrg_result.json"`
  - `MERGED_PDF_PATTERN = "merged-{index:03d}.pdf"`
  - `MERGED_MD_PATTERN = "merger-{index:03d}.md"`
  - `SCORE_THRESHOLD = 5.0`
- Add typed payload aliases for planner/apply handoff to keep schema validation centralized.

### Signature Sketch
```python
# src/md_mrg/planner.py
def run_plan(source_dir: Path, cfg: MdMrgConfig) -> dict: ...

# src/md_mrg/apply.py
def run_apply(source_dir: Path, cfg: MdMrgConfig) -> dict: ...
```

### Exit Criterion
- All md_mrg module files exist with import-safe structure and constants required by plan/apply contracts.

### Validation Command
```bash
uv run python -c "import md_mrg.cli, md_mrg.planner, md_mrg.apply; print('ok')"
```

## Phase 2: Configuration Integration For md_mrg

Implementing requirements from Analysis Section 2 (`src/common/config.py`, settings files), Analysis Section 3 (fail-fast config errors), and Analysis Section 4 (config validation checklist).

### Steps
- Extend `src/common/config.py` with md_mrg-specific typed settings while preserving md_gen behavior:
  - Add dataclass for md_mrg prompt/runtime settings.
  - Add parser helper for `md_mrg.score.prompt_path`.
  - Reuse existing `language_model` settings for planner gateway runtime.
- Keep existing `build_config_from_args` behavior intact for md_gen callers; add dedicated md_mrg config builder used by md_mrg CLI.
- Add explicit `ConfigValidationError` codes for md_mrg key/path validation failures.
- Align config shape in both files:
  - `data/config/settings-default.json`
  - `data/config/settings.json`

### Signature Sketch
```python
# src/common/config.py
@dataclass(frozen=True)
class MdMrgSettings:
    score_prompt_path: Path

@dataclass(frozen=True)
class MdMrgConfig:
    source_dir: Path
    language_model: LlamaModelSettings
    md_mrg: MdMrgSettings

def build_md_mrg_config_from_args(args: SimpleNamespace) -> MdMrgConfig: ...
```

### Exit Criterion
- md_mrg config can be built independently, validates required keys, and does not regress md_gen config tests.

### Validation Command
```bash
uv run pytest -q test/common/test_config.py
```

## Phase 3: CLI Orchestration With Mandatory Mode Flags

Implementing requirements from Analysis Section 2 (`src/md_mrg/cli.py`), Analysis Section 3 (argument/config/runtime errors), and Analysis Section 4 (CLI rejection/dispatch checklist).

### Steps
- Build parser with:
  - mandatory `--source`
  - mutually exclusive, required mode flags: `--plan` and `--apply`
- Keep CLI as orchestration only:
  - parse args
  - build md_mrg config via `common.config`
  - dispatch to planner or apply module
  - map known validation/runtime exceptions to deterministic exit codes/messages
- Disallow silent fallthrough paths (always return an explicit exit code).

### Pseudocode
```text
args = parse_args()
cfg = build_md_mrg_config_from_args(args)
if args.plan:
    run_plan(cfg.source_dir, cfg)
elif args.apply:
    run_apply(cfg.source_dir, cfg)
return 0
```

### Exit Criterion
- CLI enforces exactly one mode, validates source, and dispatches without embedding plan/apply logic.

### Validation Command
```bash
uv run pytest -q test/md_mrg/test_mrg_plan.py -k "cli"
```

## Phase 4: Planner Implementation (batch.json -> batch_mrg.json)

Implementing requirements from Analysis Section 1 (planner flow), Analysis Section 2 (`src/md_mrg/planner.py`), Analysis Section 3 (boundary/failure behavior), and Analysis Section 4 (adjacent scoring, threshold, ordering, singleton, prompt envelope).

### Steps
- Load and validate input JSON from `{source}/batch.json`:
  - Ensure root object with `documents` list (fallback deterministic empty behavior).
- Partition records:
  - image records (`file_type == "image"`) for scoring/grouping
  - pdf records (all non-image finalized docs) for passthrough
- Build adjacent-only scoring loop over image records.
- Create score prompt payload exactly as required:
  - Page A section markers
  - Page B section markers
  - markdown text loaded from each record's `markdown_file`
- Invoke `LlamaLanguageGateway.send_text_request(TextRequest(...))` and parse score from model output JSON.
- Grouping algorithm:
  - Continue group when `abs(score) >= 5`
  - If score negative and threshold met: place Page B before Page A inside current group, then continue comparisons anchored on prior Page A position
  - Split group when `abs(score) < 5` or scoring/parsing fails
  - Emit singleton image groups as `{ "documents": [single_doc] }`
- Serialize deterministic planner result to `{source}/batch_mrg.json` with strict order:
  1) all image group objects
  2) original pdf document records unchanged

### Pseudocode
```text
groups = []
active_group = [images[0]]
for each adjacent pair (A, B):
  score = score_pair(A, B)  # may fail -> boundary split
  if failed or abs(score) < 5:
    flush(active_group)
    active_group = [B]
    continue
  if score >= 0:
    append B to active_group
  else:
    reorder active_group so B is inserted before A
    anchor next comparison on A
flush(active_group)
output = [group_obj(g) for g in groups] + pdf_records
```

### Exit Criterion
- Planner produces deterministic `batch_mrg.json`, only scores adjacent image pairs, preserves pdf records, and continues on pair failures.

### Validation Command
```bash
uv run pytest -q test/md_mrg/test_mrg_plan.py -k "plan or planner"
```

## Phase 5: Apply Implementation (batch_mrg.json -> merged outputs + result)

Implementing requirements from Analysis Section 1 (apply flow), Analysis Section 2 (`src/md_mrg/apply.py`), Analysis Section 3 (failure isolation, non-destructive behavior), and Analysis Section 4 (naming, cleanup, continuation, result file).

### Steps
- Load `{source}/batch_mrg.json` and validate mixed item shapes:
  - group object: `{ "documents": [...] }`
  - standalone pdf record object
- Iterate work items in listed order and maintain deterministic group counter (`001`, `002`, ...).
- For each image group:
  - Merge markdown files in listed order into `{source}/merger-NNN.md`
  - Merge source images in listed order into `{source}/merged-NNN.pdf`
  - Delete loose source markdown only after both merged artifacts succeed
  - Never delete original images
- For standalone pdf records:
  - Record passthrough status (`ok`) without destructive file operations
- Error isolation:
  - Catch per-item exceptions
  - Record failed status
  - Continue processing remaining items
- Persist run result to `{source}/batch_mrg_result.json` with per-item statuses (`ok`/`failed`) and diagnostic message field for failures.

### Signature Sketch
```python
# src/md_mrg/apply.py
def merge_group_markdown(source_dir: Path, documents: list[dict], output_md: Path) -> None: ...
def merge_group_images_to_pdf(source_dir: Path, documents: list[dict], output_pdf: Path) -> None: ...
def run_apply(source_dir: Path, cfg: MdMrgConfig) -> dict: ...
```

### Exit Criterion
- Apply creates deterministic merged outputs, performs safe cleanup only after success, continues after failures, and writes `batch_mrg_result.json`.

### Validation Command
```bash
uv run pytest -q test/md_mrg/test_mrg_units.py -k "apply"
```

## Phase 6: Tests Rewrite And Expansion

Implementing requirements from Analysis Section 2 (test files impact), Analysis Section 3 (edge cases), and Analysis Section 4 (verification checklist coverage).

### Steps
- Rewrite `test/md_mrg/test_mrg_plan.py` to remove legacy `merge-plan.json`/legacy modules assumptions and cover:
  - CLI mode/source validation behavior
  - planner output contract (`batch_mrg.json`)
  - adjacent-only comparisons
  - image-groups-before-pdf ordering
  - abs-threshold split/continue logic
  - negative-score reorder semantics
  - scoring/parsing failure continuation
- Rewrite `test/md_mrg/test_mrg_units.py` for planner/apply utilities:
  - prompt envelope exact markers for Page A/Page B
  - deterministic naming sequence
  - markdown cleanup only on success
  - no source image deletion
  - per-group apply continuation and status persistence
- Extend `test/common/test_config.py` with md_mrg config presence/error-code tests while preserving existing md_gen assertions.

### Exit Criterion
- Tests fully reflect the new md_mrg architecture and verify all locked behaviors from Analysis Section 4.

### Validation Command
```bash
uv run pytest -q test/common/test_config.py test/md_mrg/test_mrg_plan.py test/md_mrg/test_mrg_units.py
```

## Phase 7: Documentation And CLI Usage Alignment

Implementing requirements from Analysis Section 2 (`docs/internals/md_mrg.md`, `README.md`) and Analysis Section 4 (documentation checklist).

### Steps
- Update `docs/internals/md_mrg.md` (currently empty) with:
  - planner/apply architecture
  - `batch_mrg.json` schema (group object and pdf entry forms)
  - `batch_mrg_result.json` schema and status semantics
  - ordering guarantees and failure continuation behavior
  - non-deletion guarantee for original images
- Update `README.md` to replace legacy subcommand contract and artifacts with:
  - `md-mrg --plan --source ...`
  - `md-mrg --apply --source ...`
  - current outputs: `batch_mrg.json`, `batch_mrg_result.json`, `merged-NNN.pdf`, `merger-NNN.md`

### Exit Criterion
- Internal docs and README exactly match implemented md_mrg behavior and artifact names.

### Validation Command
```bash
uv run pytest -q
```

## Final Delivery Gate

Implementing requirements from Analysis Section 4 (full verification checklist closure).

### Steps
- Execute checklist-driven verification in this order:
  1. CLI contract tests
  2. Planner behavior tests
  3. Apply behavior tests
  4. Config regression tests
  5. Documentation consistency pass
- Run full suite and confirm no regressions outside md_mrg scope.
- Ensure deterministic artifacts for repeat runs are documented (overwrite/collision behavior explicitly decided in code and tests).

### Exit Criterion
- Every item in Analysis Section 4 is satisfied by code and tests, and full test suite passes.

### Validation Command
```bash
uv run pytest -q
```