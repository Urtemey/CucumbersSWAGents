---
name: fix-bug
description: "Investigate, fix, and test a bug"
argument-hint: "<bug description or issue number>"
---

# /fix-bug — Bug Fix Pipeline

### Step 1: Investigation
1. Delegate to `debugger` agent
2. If issue number given — fetch via `gh issue view`
3. Agent conducts RCA, documents in `docs/rca/`

### Step 2: Review RCA
1. Present root cause and proposed fix to user
2. **STOP — wait for approval**

### Step 3: Fix
1. Delegate to `implementer` agent
2. Apply fix per RCA

### Step 4: Test
1. Delegate to `tester` agent
2. Write regression test for this bug
3. Verify all existing tests pass

### Step 5: Code Review
1. Delegate to `code-reviewer` agent
2. Verify no Critical findings

### Step 6: Summary
```
## Bug Fix Report
- **Bug**: description
- **Root Cause**: cause
- **Fix**: what changed
- **Tests**: regression tests added
- **Files Changed**: list
```
