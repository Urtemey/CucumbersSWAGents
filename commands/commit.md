# /commit — Stage and Commit Changes

## Instructions

1. Run `git status` to see all changed and untracked files.
2. Run `git diff` to review both staged and unstaged changes.
3. Run `git log --oneline -5` to see recent commit message style.
4. Analyze changes and determine the type:
   - `feat:` — New feature
   - `fix:` — Bug fix
   - `chore:` — Maintenance, dependencies, config
   - `docs:` — Documentation only
   - `refactor:` — Code restructuring, no behavior change
   - `test:` — Adding or updating tests
5. Draft a concise commit message (1-2 sentences) following Conventional Commits.
6. Stage specific files (`git add <file>`) — never use `git add .` or `git add -A`.
7. Create the commit.
8. Run `git status` to confirm success.

## Rules

- **NEVER** push unless the user explicitly asks.
- **NEVER** commit `.env`, credentials, secrets, or API keys.
- **NEVER** use `--amend` unless the user explicitly asks.
- If the user provides a message, use it. Otherwise, generate one from the diff.
- Message should focus on the "why", not the "what".
