---
name: commit
description: "Stage and commit with conventional commit message"
argument-hint: "[commit message]"
---

# /commit — Commit Changes

## Rules
- Use conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`
- NEVER push without explicit user request
- NEVER commit .env, secrets, credentials
- If no message provided — generate from diff

## Workflow
1. `git status` — see what changed
2. `git diff` — analyze changes
3. `git log --oneline -5` — match commit style
4. Determine change type (feat/fix/chore/...)
5. Generate commit message
6. Stage specific files (not `git add .`)
7. Create commit
8. Show `git status` result
