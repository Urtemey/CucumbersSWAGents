# /plan — Create a Detailed Implementation Plan

## Arguments
`/plan "<task or feature description>"`

## Instructions

### Step 1: Understand Context
1. Read `PROJECT.md` for tech stack, conventions, and commands.
2. Read `Agent.md` for behavioral rules.
3. If a PRD exists, read it from `docs/prds/`.
4. Explore relevant existing code and architecture.

### Step 2: Analyze
1. Break the task into logical phases with clear boundaries.
2. Identify dependencies between phases.
3. Identify risks, unknowns, and assumptions.
4. Estimate relative complexity per phase.

### Step 3: Create Plan
Save to `docs/plans/[task-name].md`:

```markdown
# Plan: [Task Name]

**Created**: YYYY-MM-DD
**PRD**: [link to PRD if applicable]
**Branch**: [suggested branch name]

## Overview
Brief description of the approach and key decisions.

## Phases

### Phase 1: [Name]
- **Goal**: What this phase achieves
- **Tasks**:
  - [ ] Task 1 — description
  - [ ] Task 2 — description
  - [ ] Task 3 — description
- **Deliverables**: What's produced
- **Dependencies**: What must be done first
- **Validation**: How to verify this phase is complete

### Phase 2: [Name]
...

### Phase 3: [Name]
...

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Risk 1 | Description | Plan |

## Assumptions
- Assumption 1
- Assumption 2

## Definition of Done
- [ ] All acceptance criteria covered
- [ ] Tests pass with required coverage
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Build succeeds
```

### Step 4: Present
Show the plan to the user and wait for feedback before execution.
