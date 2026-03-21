---
name: execute
description: "Execute an implementation plan step by step"
argument-hint: "<plan file path>"
---

# /execute — Execute Plan

### Step 1: Load Plan
1. Read specified plan file
2. Identify current phase (first uncompleted)
3. Load context: PRD, design doc

### Step 2: Execute Phase
For each phase:
- Read description and tasks
- Delegate to `implementer` for implementation
- Mark tasks as completed in plan file
- Run validation (lint, types, tests)

### Step 3: Validate
- After each phase — run `/validate`
- Fix issues before proceeding to next phase

### Step 4: Report
- Update task statuses in plan file
- Output brief phase completion report
