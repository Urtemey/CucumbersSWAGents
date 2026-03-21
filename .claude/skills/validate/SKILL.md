---
name: validate
description: "Full project validation: lint, types, tests, build, quality"
---

# /validate — Full Project Health Check

### Checks (in order)

1. **Lint** — Run lint command from PROJECT.md. Zero errors.
2. **Type Check** — Run type checker from PROJECT.md. Zero errors.
3. **Tests** — Run tests from PROJECT.md. All pass. Check coverage.
4. **Build** — Run build from PROJECT.md. Must succeed.
5. **Quality Scan** — Search for hardcoded secrets, dead code, swallowed errors, dep sync issues.

### Output
```
## Validation Report

| Check | Status | Details |
|-------|--------|---------|
| Lint | PASS/FAIL | N errors |
| Types | PASS/FAIL | N errors |
| Tests | PASS/FAIL | N/M passed |
| Build | PASS/FAIL | — |
| Quality | PASS/FAIL | findings |

**Overall: PASS / FAIL**
```
