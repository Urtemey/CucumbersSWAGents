---
name: new-feature
description: "Full feature pipeline: PRD → design → implement → test → review"
argument-hint: "<feature description>"
---

# /new-feature — Full Feature Development Pipeline

### Phase 1: PRD Creation
1. Delegate to `product-manager` agent
2. Create PRD using `docs/templates/PRD-TEMPLATE.md`
3. Save to `docs/prds/[feature-name].md`
4. **STOP — wait for user approval**

### Phase 2: Technical Design
1. Delegate to `architect` agent
2. Read PRD, create design document
3. Include: components, API contracts, data models, phase breakdown
4. **STOP — wait for user approval**

### Phase 3: Implementation Plan
1. Create plan based on design
2. Break into phases with clear deliverables
3. Save to `docs/plans/[feature-name].md`

### Phase 4: Implementation
1. Delegate to `implementer` agent (one phase at a time)
2. After each phase — run linter and type checker

### Phase 5: Testing
1. Delegate to `tester` agent
2. Every acceptance criterion → test
3. All tests must pass

### Phase 6: Code Review
1. Delegate to `code-reviewer` agent
2. All Critical findings must be fixed
3. Iterate with implementer if needed

### Phase 7: Summary
- What was implemented
- Files changed/created
- Test status
- Open items (if any)
