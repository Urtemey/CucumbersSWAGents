---
name: refactor
description: "Refactor code while preserving behavior"
argument-hint: "<what to refactor>"
---

# /refactor — Behavior-Preserving Refactoring

### Step 1: Read target code, identify existing tests, run baseline
### Step 2: Plan refactoring, propose changes, **wait for approval**
### Step 3: Apply changes, run tests after each change
### Step 4: All existing tests must still pass. No behavior changes.

## Rules
- Tests MUST pass before AND after
- No behavior changes — refactoring only
- If tests don't exist, write characterization tests FIRST
