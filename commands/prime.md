# /prime — Load Project Context

## Instructions

Load the full project context into the conversation by reading these sources in order:

### Step 1: Core Documentation
1. `Agent.md` — Behavioral contract and development rules.
2. `PROJECT.md` — Tech stack, commands, conventions (if exists).

### Step 2: Active Work
1. Check for any active PRDs in `docs/prds/`.
2. Check for any active plans in `docs/plans/`.

### Step 3: Codebase
1. Read the project's directory structure.
2. Identify key entry points and configuration files.
3. Note any README or setup instructions.

### Step 4: Git State
1. `git status` — Current changes.
2. `git log --oneline -10` — Recent commits.
3. `git branch` — Current and available branches.

### Step 5: Summary
Present a concise summary:
```markdown
## Project Context Loaded

- **Project**: [name]
- **Stack**: [language, framework, etc.]
- **Branch**: [current branch]
- **Recent work**: [last few commits]
- **Active PRDs**: [list or "none"]
- **Active Plans**: [list or "none"]
- **Uncommitted changes**: [yes/no + summary]
```
