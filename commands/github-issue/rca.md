# /github-issue/rca — Root Cause Analysis for GitHub Issues

## Arguments
`/github-issue/rca #<issue-number>`

## Instructions

### Step 1: Fetch Issue
1. Run `gh issue view <number>` to get issue details.
2. Read title, description, labels, and comments.
3. Extract reproduction steps if provided.

### Step 2: Investigate
1. Search the codebase for code mentioned in or related to the issue.
2. Review git history: `git log --oneline --all -- <relevant-files>`.
3. Look for recent changes that might have introduced the issue.
4. Analyze stack traces or error messages from the issue.

### Step 3: Root Cause Analysis
Determine:
- **What** is the actual root cause (not just the symptom)?
- **When** was it introduced (which commit/PR)?
- **Why** did it happen (gap in testing, unclear requirements, etc.)?
- **Where** in the code is the fix needed?

### Step 4: Document
Save RCA to `docs/rca/issue-<number>.md`:

```markdown
# RCA: Issue #<number> — [Title]

**Date**: YYYY-MM-DD
**Issue**: [GitHub issue link]
**Severity**: Critical / High / Medium / Low
**Status**: Investigated / Fix proposed / Fixed

## Symptoms
- What users/systems observed

## Timeline
- When the issue was first reported
- When it was likely introduced (commit/PR)

## Root Cause
Technical explanation of WHY the bug exists.

## Impact
- Who/what is affected
- Scope of the problem

## Suggested Fix
- Specific code changes needed
- Files to modify
- Approach and rationale

## Prevention
- What testing/process would have caught this?
- Recommendations for avoiding similar issues
```

### Step 5: Report
Present the RCA summary to the user with a recommended next step:
- `/fix-bug #<number>` to implement the fix
- Or manual action if the fix requires human judgment
