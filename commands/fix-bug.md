# /fix-bug — Investigate and Fix a Bug

## Arguments
`/fix-bug <bug description>` or `/fix-bug #<issue-number>`

## Instructions

### Step 1: Investigate
- If an issue number is provided, fetch it: `gh issue view <number>`
- Understand the symptoms: what's broken, when it started, who's affected.
- Search the codebase for related code.
- Review git history for recent changes in the affected area.
- Reproduce the bug if possible.

### Step 2: Root Cause Analysis
- Identify the root cause (not just the symptom).
- Document findings clearly:
  - **Symptoms**: What was observed
  - **Root Cause**: Why it happened
  - **Impact**: What's affected
  - **Suggested Fix**: Specific changes needed

### Step 3: Fix
- Implement the fix based on the RCA.
- Make the minimal change necessary — don't refactor unrelated code.
- Follow existing code patterns.

### Step 4: Test
- Write a regression test that reproduces the original bug.
- The test should FAIL without the fix and PASS with it.
- Run the full test suite to verify no regressions.

### Step 5: Code Review
- Self-review the changes:
  - Is the fix correct and complete?
  - Are there security implications?
  - Could this fix cause other issues?
  - Is the regression test adequate?

### Step 6: Summary
```markdown
## Bug Fix Summary
- **Bug**: [description]
- **Root Cause**: [why it happened]
- **Fix**: [what was changed]
- **Regression Test**: [test file and name]
- **Files Changed**: [list]
- **Confidence**: High/Medium/Low
```
