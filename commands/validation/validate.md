# /validation/validate — Full Project Health Check

## Instructions

Run all validation checks in order. Stop at first failure category if Critical.

### 1. Lint
- Run the lint command from `PROJECT.md`.
- Zero errors required.
- Report: pass/fail + error count.

### 2. Type Check
- Run the type check command from `PROJECT.md`.
- Zero errors required.
- Report: pass/fail + error count.

### 3. Tests
- Run the test command from `PROJECT.md`.
- All tests must pass.
- Report: pass/fail + passed/total count.
- Check coverage threshold if configured.

### 4. Build
- Run the build command from `PROJECT.md`.
- Must complete successfully.
- Report: pass/fail.

### 5. Code Quality Scan
Manual checks:
- [ ] No hardcoded secrets (search for `password`, `secret`, `api_key`, `token` in source)
- [ ] No dead code (unused imports, unreachable branches)
- [ ] No swallowed errors (empty catch/except blocks)
- [ ] Dependencies in sync (lock file matches manifest)

### Output

```markdown
## Validation Report

| Check | Status | Details |
|-------|--------|---------|
| Lint | ✅ PASS / ❌ FAIL | N errors |
| Types | ✅ PASS / ❌ FAIL | N errors |
| Tests | ✅ PASS / ❌ FAIL | N/M passed |
| Build | ✅ PASS / ❌ FAIL | — |
| Quality | ✅ PASS / ❌ FAIL | findings |

**Overall: ✅ PASS / ❌ FAIL**
```

If any check fails, list specific errors and suggest fixes.
