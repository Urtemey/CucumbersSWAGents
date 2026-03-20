# /review-code — Structured Code Review

## Arguments
`/review-code` (reviews current diff) or `/review-code <file-path>`

## Instructions

### Step 1: Identify Changes
- If no file specified: `git diff HEAD` for all current changes.
- If file specified: read and analyze that file.
- Understand the purpose of the changes from commit messages or PRD.

### Step 2: Code Review Checklist

**Correctness**
- Does the code do what the PRD/requirements specify?
- Are edge cases handled?
- Is the logic correct?

**Security**
- No SQL injection, XSS, or command injection vectors?
- No hardcoded secrets or credentials?
- Input validation at system boundaries?
- Authentication/authorization checks in place?

**Performance**
- No N+1 queries?
- No unnecessary loops or redundant operations?
- No memory leaks (unclosed resources, growing collections)?
- Appropriate data structures used?

**Readability**
- Clear, descriptive names?
- No deep nesting (max 3 levels)?
- Functions are focused and short?
- Comments explain "why", not "what"?

**Tests**
- Are acceptance criteria covered by tests?
- Are edge cases tested?
- Are error paths tested?
- Test names describe behavior?

**Error Handling**
- Errors caught and handled appropriately?
- No swallowed exceptions (empty catch blocks)?
- User-facing errors are helpful?
- Errors are logged with context?

### Step 3: Test Validation
- Run the test suite if possible.
- Report any failures.

### Step 4: Report
```markdown
## Code Review Report

### Critical (blocks merge)
- [file:line] Description → Suggested fix

### Warning (should fix)
- [file:line] Description → Suggested fix

### Suggestion (nice to have)
- [file:line] Description → Suggested improvement

### Summary
- **Verdict**: Approve / Request Changes
- **Risk Level**: Low / Medium / High
- **Test Coverage**: Adequate / Needs improvement
```
