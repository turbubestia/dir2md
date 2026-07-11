---
name: implementation-analysis
description: Analyzes what technical steps are needed based on issue.plan.request.md and updates issue.plan.analysis.md
user-invocable: true
---

# Instructions
Read the contents of `issue.plan.request.md` in the workspace root. 

## Rules
- Analyze the code base architecture.
- Identify the exact files, modules, classes, or patterns that need to change.
- Detail the data structures or logic modifications required.
- Target file: Write or update the file `issue_name.plan.analysis.md` in the `./issues` directory where `issue_name` corresponds to the name in the attached file's name if provided or the current branch name otherwise.
- The user will add tag with **User: [user message]** to indicate their input and must be considered for the current refinement process and the document must be updated acordingly.
- This is an analysis that responds to the question of what needs to be done to complete the request outlined in the file `issue.plan.request.md` or a previous version of the analysis file `issue_name.plan.analysis.md`. It should not include actual code changes, only the steps and modifications required.
- The analysis does not respond to how the changes should be implemented; it only outlines what needs to be done.
- Don't write code as part of this step.