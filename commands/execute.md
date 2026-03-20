# /execute — Execute an Implementation Plan

## Arguments
`/execute <path-to-plan-file>`

## Instructions

1. **Load the plan** — Read the specified plan file from `docs/plans/`.
2. **Load context** — Read the associated PRD, design doc, and `PROJECT.md`.
3. **Identify current phase** — Find the first uncompleted phase in the plan.
4. **For each phase:**
   a. Read the phase description and task list.
   b. Read relevant existing code to understand patterns.
   c. Implement each task in order.
   d. Run validation after each task (lint, types, tests).
   e. Mark tasks as completed in the plan file.
5. **After each phase:**
   - Run full validation (lint + types + tests + build).
   - Fix any issues before moving to the next phase.
   - Report phase completion status.
6. **Final report:**
   - Summary of what was implemented.
   - Files created/modified.
   - Test results.
   - Any deviations from the plan and why.

## Rules

- One phase at a time — don't skip ahead.
- Follow existing code patterns from `PROJECT.md`.
- Stop and ask if requirements are ambiguous.
- Update the plan file with completion status as you go.
