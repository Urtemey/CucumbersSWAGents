# AGENTS.md — Universal Behavioral Contract for AI Coding Agents

> If multiple AI tools work in this repository, AGENTS.md acts as the shared behavioral contract for all automated coding agents.

---

## 1. Project Overview

This project follows **PRD-driven development**. Every feature starts with a Product Requirements Document before any code is written.

### Documentation Structure
```
docs/prds/         — Product Requirements Documents
docs/architecture/ — Architecture decisions and diagrams
docs/plans/        — Implementation plans
docs/templates/    — Reusable templates
```

### Key Files
- `Agent.md` — This file. Behavioral contract for all AI agents.
- `Create-PRD.md` — PRD template and creation guide.
- `PROJECT.md` — Project-specific configuration (tech stack, commands, conventions).
- `commands/` — Slash command definitions for workflow automation.
- `my-skill/` — Custom skill definitions.

---

## 2. Development Principles

1. **Single Responsibility** — Each function/module does one thing well.
2. **Readability First** — Code is read more often than written. Optimize for the reader.
3. **Consistency** — Follow existing patterns in the codebase. Don't introduce new patterns without justification.
4. **Predictable Behavior** — No surprises. Functions do what their names suggest.
5. **Minimal Scope** — Implement exactly what the PRD specifies. No gold-plating.

---

## 3. PRD-Driven Development

### Source of Truth
All feature requirements live in `docs/prds/`. Agents MUST read the relevant PRD before implementing.

### Acceptance Criteria Format
Every acceptance criterion uses GIVEN/WHEN/THEN:

```
GIVEN [precondition]
WHEN [action]
THEN [expected result]
```

### Workflow
1. PRD is created (manually or via `/new-feature`)
2. PRD is reviewed and approved by human
3. Implementation follows PRD exactly
4. Tests validate each acceptance criterion
5. Code review verifies PRD compliance

---

## 4. Code Style Rules

- **Short functions** — Max 20-30 lines. Extract when longer.
- **No deep nesting** — Max 3 levels of indentation. Use early returns.
- **No global mutable state** — Pass dependencies explicitly.
- **Prefer pure functions** — Same input → same output, no side effects.
- **Validate inputs at boundaries** — System edges (API, user input, external services), not internal calls.
- **Meaningful names** — Variables/functions describe WHAT, not HOW.
- **No magic numbers** — Use named constants.

---

## 5. Testing Requirements

- Every acceptance criterion in the PRD needs at least one test.
- No real external services in tests — use mocks, stubs, or test doubles.
- Test organization follows `PROJECT.md` conventions.
- Test names describe behavior: `should [expected] when [condition]`.
- Use Arrange/Act/Assert pattern.
- Tests must be deterministic — no flaky tests.

---

## 6. Security Rules

- **NEVER** log tokens, passwords, API keys, or PII.
- **NEVER** commit `.env` files, credentials, or secrets.
- **NEVER** hardcode secrets in source code.
- Validate ALL external inputs (user input, API responses, file contents).
- Use parameterized queries — never string-concatenate SQL.
- Follow OWASP Top 10 guidelines.

---

## 7. Git Workflow

### Branch Naming
```
feat/short-description    — New features
fix/short-description     — Bug fixes
chore/short-description   — Maintenance, deps, config
docs/short-description    — Documentation changes
refactor/short-description — Code refactoring
```

### Commit Messages (Conventional Commits)
```
feat: add user registration endpoint
fix: resolve null pointer in payment flow
chore: update dependencies to latest
docs: add API documentation for auth
refactor: extract validation into shared module
test: add integration tests for order service
```

### Rules
- PRs required for all changes.
- No direct commits to `main` or `master`.
- Each PR should be focused — one logical change per PR.
- Squash commits when merging if history is messy.

---

## 8. Implementation Workflow

### 4-Step Process

**Step 1: Requirements**
- Read the PRD
- Understand acceptance criteria
- Clarify ambiguities before coding

**Step 2: Implementation**
- Follow the plan/design document
- One phase at a time
- Stick to existing code patterns

**Step 3: Testing**
- Write tests for each acceptance criterion
- Run full test suite
- Verify no regressions

**Step 4: Validation**
- Lint check (zero errors)
- Type check (zero errors)
- All tests pass
- Build succeeds

---

## 9. Agent Permissions

### Allowed (Always)
- Read any project file
- Modify files within the scope of the current task
- Create feature branches
- Run tests, linters, type checkers, builds
- Create and update documentation

### Requires Approval
- Adding new dependencies
- Changing database schemas
- Modifying API contracts
- Altering CI/CD pipelines
- Changing authentication/authorization logic

### Forbidden
- Committing secrets, tokens, or credentials
- Removing security measures or guards
- Skipping tests to meet deadlines
- Pushing directly to main/master
- Making changes outside the scope of the current task

---

## 10. Quality Standards

Before marking any task as complete:

- [ ] All PRD acceptance criteria are satisfied
- [ ] All tests pass
- [ ] Coverage meets project thresholds (see `PROJECT.md`)
- [ ] Lint passes with zero errors
- [ ] Type check passes with zero errors
- [ ] Build succeeds
- [ ] No Critical code review findings open

---

## 11. Documentation Rules

- Keep documentation in sync with implementation.
- Update docs in the SAME PR as code changes.
- API documentation must include request/response examples.
- Architecture decisions must include rationale.
- Use Mermaid for diagrams when possible.

---

## 12. Validation Checklist

Run before completing any task:

```
□ PRD read and understood
□ All acceptance criteria implemented
□ Tests written and passing
□ Lint clean
□ Types clean
□ Build successful
□ Documentation updated
□ No secrets in code
□ Code review findings addressed
□ Git history is clean
```
