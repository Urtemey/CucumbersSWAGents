---
name: plan
description: "Create a detailed implementation plan"
argument-hint: "<feature or task description>"
---

# /plan — Create Implementation Plan

### Step 1: Context Loading
1. Read `PROJECT.md` for tech stack
2. Read `CLAUDE.md` for workflow rules
3. Study existing code and architecture

### Step 2: Analysis
1. Break task into logical phases
2. Identify dependencies between phases
3. Identify risks and unknowns

### Step 3: Plan Creation
Save to `docs/plans/[task-name].md`:

```markdown
# Plan: [Task Name]

## Overview
Brief description of approach and key decisions.

## Phases

### Phase 1: [Name]
- **Goal**: what this achieves
- **Tasks**: [ ] task 1, [ ] task 2
- **Deliverables**: what's produced
- **Validation**: how to verify completion

## Risks
- Risk → Mitigation

## Definition of Done
- [ ] All acceptance criteria covered
- [ ] Tests pass
- [ ] Code review completed
- [ ] Documentation updated
```
