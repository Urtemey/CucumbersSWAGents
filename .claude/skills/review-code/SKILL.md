---
name: review-code
description: "Structured code review of recent changes"
argument-hint: "[file path]"
---

# /review-code — Code Review

### Step 1: Identify Changes
- No file specified: `git diff HEAD` for all changes
- File specified: analyze that file

### Step 2: Review
Delegate to `code-reviewer` agent with checklist:
- Correctness, Security, Performance
- Readability, Test coverage, Error handling

### Step 3: Report
Structured report with severity levels:
- **Critical** — blocks merge
- **Warning** — should fix
- **Suggestion** — nice to have

### Step 4: Action
If Critical findings exist — propose automatic fixes.
