---
name: rca
description: "Root Cause Analysis for a GitHub issue"
argument-hint: "<issue number or description>"
---

# /rca — Root Cause Analysis

1. Fetch issue via `gh issue view` (if number given)
2. Delegate to `debugger` agent
3. Search codebase, review git history, analyze errors
4. Document RCA in `docs/rca/issue-N.md`
5. Recommend next step: `/fix-bug` or manual action
