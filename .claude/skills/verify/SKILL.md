---
name: verify
description: "Final verification before merge — comprehensive pre-merge checklist"
---

# /verify — Pre-Merge Verification

### Checklist
1. **Code Quality** — Lint passes, types clean, no dead code, no secrets
2. **Tests** — All pass, coverage met, new code tested, ACs covered
3. **Documentation** — PRD satisfied, README updated, API docs updated
4. **Git** — Clean history, conventional commits, branch up to date
5. **Review** — Code review done, no Critical findings, no unresolved threads

### Output
```
READY TO MERGE — all checks pass
```
or
```
NOT READY — N issues found:
1. issue description
2. issue description
```
