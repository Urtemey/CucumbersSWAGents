---
name: prime
description: "Load project context into conversation"
---

# /prime — Load Project Context

### Step 1: Core Docs
1. `CLAUDE.md` — team config and workflow
2. `PROJECT.md` — tech stack and conventions

### Step 2: Project State
1. `docs/state/STATE.md` — current session state
2. Recent PRDs from `docs/prds/`
3. Active plans from `docs/plans/`

### Step 3: Git State
1. `git status` — current changes
2. `git log --oneline -10` — recent commits
3. `git branch` — current branch

### Step 4: Summary
```
## Project Context Loaded
- **Project**: name and stack
- **Branch**: current branch
- **Active PRDs**: list or none
- **Active Plans**: list or none
- **Uncommitted changes**: yes/no
```
