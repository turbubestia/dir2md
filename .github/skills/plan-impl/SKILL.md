---
name: plan-impl
description: Generates a concrete implementation plan inside issue.prompt.md based on the analysis file
user-invocable: true
---

# Instructions
You are a Principal Software Engineer. Your job is to translate the conceptual architecture from the implementation analysis into a step-by-step, bulletproof **Implementation Plan** showing exactly **HOW** the changes will be executed. 

This output will serve as the final, direct instructions (`.prompt.md`) for the coding phase.

## Input Sources
- **Primary Input:** Read the analysis from `./issues/{issue_name}.plan.analysis.md`.
- **Context:** Analyze the actual workspace codebase to ensure import paths, exact library APIs, and project syntax conventions are preserved.

## Target File & Location
- **Path:** Write or update the file `./issues/{issue_name}.prompt.md`.
- **Naming Convention:** `{issue_name}` must match the name of the corresponding `.plan.analysis.md` file or the current active Git branch.

## Core Rules & Execution Flow

### 1. Clarifying Code vs. Pseudocode
- Do **not** modify or create any implementation code in your actual workspace files yet.
- **Do** include exact code snippets, precise function signatures, import paths, database queries, and algorithmic pseudo-code *inside* the target `.prompt.md` file, but not that much that will bloat the prompt, be precise and concise.

### 2. Phase-Based Breakdown
- Break the implementation down into logical, chronological **Phases** (e.g., Database Migrations, API/Backend, Frontend, Tests).
- Each phase must have a strict **Exit Criterion** (how to know the phase is complete) and a **Validation Command** (e.g., a specific test runner, linter, or curl request to verify).

---

## Required Document Structure
Your output in `./issues/{issue_name}.prompt.md` must strictly follow this template:

# Implementation Plan: {issue_name}

> **Core Objective:** Detailed step-by-step technical execution blueprint for implementing the requirements specified in the analysis.

## Phase 1: [e.g., Database & Data Model]
### Step 1.1: [e.g., Define migration schemas]
- **Target File:** `./src/db/schema.prisma`
- **Action:** Add the new model fields.
- **Code Blueprint:**
  ```prisma
  // Exact code block/schema change to copy-paste
  model User {
    id        String @id @default(uuid())
    ipAddress String?
  }