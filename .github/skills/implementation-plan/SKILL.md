---
name: implementation-plan
description: Generates a concrete implementation plan inside issue.prompt.md based on the analysis file
user-invocable: true
---

# Instructions
Read `issue.plan.analysis.md` from the workspace root.

## Rules
- Provide the final concrete implementation plan, including exact pseudo-code or step-by-step code blocks needed to solve the request.
- Target file: Write or update the file `issue_name.plan.prompt.md` in the `./issues` directory where `issue_name` corresponds to the name in the attached file's name if provided or the current branch name otherwise.
- Write detailed steps, phases, and todos with exit criteria and validations.
- Ensure that each step is actionable and clearly linked to the analysis provided in `issue.plan.analysis.md`.
- Do not write code yet.