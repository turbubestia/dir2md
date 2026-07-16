You are an expert technical writer and software architect. I need to update the developer documentation file `docs/internals/md_gen.md` to reflect our codebase's architecture and the recent design choices for the new OCR module.

### Context
- **Codebase Style**: Highly modular, mostly functional Python. We prioritize testability, aiming for pure functions with isolated side effects.
- **Project Structure**: Under `src/`, we have independent modules like `src/md_gen` and `src/md_mgr`. Inside each folder, individual Python files act as sub-modules dedicated to a single, specific task.
- **The Update**: We are introducing an OCR module. The design choices, requirements, and analysis for this are detailed in:
  1) `issues/15-sub1-create-ocr-module.plan.request.md`
  2) `issues/15-sub1-create-ocr-module.plan.analysis.md`

### Goal
Update (or rewrite) ONLY `docs/internals/md_gen.md` so that a brand-new developer can open it and immediately understand how the `md_gen` module works, how data flows through it, and how the new OCR capabilities integrate.

### Required Document Structure
Please structure `docs/internals/md_gen.md` with the following sections:

1. **Overview & System Flow**: 
   - A high-level explanation of what `md_gen` does.
   - A text-based flow diagram (using Markdown/Mermaid code blocks if appropriate) showing the data lifecycle (Inputs -> Transformations -> Outputs), specifically highlighting where the OCR process hooks in.
2. **Logical Architecture (Functional Modules)**:
   - A breakdown of the files inside `src/md_gen/`. 
   - For each file, explain its single responsibility and its primary input/output contract.
3. **Design Patterns & Testability**:
   - Explain *how* the functional design facilitates testing (e.g., how we isolate side-effects, use mock data, or keep functions pure). Include a brief best-practice note for developers adding new code to this module.
4. **OCR Module Integration (from Issue #15)**:
   - Detail the specific architecture choices made for the OCR module based on the provided `.plan.request.md` and `.plan.analysis.md` files.
5. How to run test or the cli to test the module

### Style Constraints
- Keep it concise, professional, and developer-centric.
- Use clear visual hierarchy (bullet points, bold text, and tables where helpful).
- Avoid overly verbose prose; focus on "how to think about this codebase."