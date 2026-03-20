# /validation/execution-report — Plan vs Reality Report

## Arguments
`/validation/execution-report <path-to-plan-file>`

## Instructions

### Step 1: Load Context
1. Read the original plan file.
2. Read git log for commits since the plan was created.
3. Review current state of implemented files.

### Step 2: Compare Plan vs Reality
For each planned task:
- Was it completed as planned? → **Completed**
- Was it done differently than planned? → **Deviated** (explain why)
- Was it not done? → **Skipped** (explain why)
- Was something done that wasn't planned? → **Unplanned** (explain why)

### Step 3: Classify Divergences
Each divergence is either:
- **Justified** — Good adaptation to unexpected circumstances (discovered complexity, better approach found).
- **Problematic** — Indicates unclear requirements, missing guardrails, or scope creep.

### Step 4: Report

```markdown
## Execution Report: [Plan Name]

**Plan**: [path to plan file]
**Date**: YYYY-MM-DD

### Summary
| Metric | Count |
|--------|-------|
| Planned tasks | N |
| Completed as planned | M |
| Deviated | K |
| Skipped | J |
| Unplanned additions | L |
| Plan adherence | X% |

### Task Details

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | description | ✅ Completed | — |
| 2 | description | ↔ Deviated | reason |
| 3 | description | ⏭ Skipped | reason |
| + | unplanned task | ➕ Added | reason |

### Divergence Analysis
1. **[Justified/Problematic]** Description — impact and recommendation

### Lessons Learned
- What worked well in the planning process
- What to improve for future plans
```
