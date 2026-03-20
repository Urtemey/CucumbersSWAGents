# /new-feature — Full Feature Development Pipeline

## Arguments
`/new-feature "<feature description>"`

## Instructions

### Phase 1: PRD Creation (Product Manager role)
1. Understand the feature request from the user.
2. Research the existing codebase for context.
3. Create a PRD following `Create-PRD.md` template.
4. Save to `docs/prds/[feature-name].md`.
5. Present the PRD to the user.
6. **⏸ STOP — Wait for user approval before proceeding.**

### Phase 2: Technical Design (Architect role)
1. Read the approved PRD.
2. Design the solution:
   - Components and their interactions
   - API contracts (request/response formats)
   - Data models / database schema
   - Technology choices with rationale
3. Break implementation into phases.
4. Present the design to the user.
5. **⏸ STOP — Wait for user approval before proceeding.**

### Phase 3: Implementation (Implementer role)
1. Create a feature branch: `feat/[feature-name]`.
2. Follow the technical design and implementation phases.
3. One phase at a time.
4. After each phase: lint, type check, run tests.
5. Follow existing code patterns from `PROJECT.md`.

### Phase 4: Testing (Tester role)
1. Map each acceptance criterion (AC-*) to test cases.
2. Write tests using Arrange/Act/Assert pattern.
3. Cover both happy paths and error cases.
4. Run full test suite — zero failures.
5. Check coverage meets project thresholds.

### Phase 5: Code Review (Code Reviewer role)
1. Review all changes for:
   - Correctness vs PRD
   - Security (OWASP Top 10)
   - Performance
   - Readability
   - Test coverage
2. Fix any Critical findings.
3. Address Warnings where reasonable.

### Phase 6: Summary
```markdown
## Feature Complete: [Feature Name]
- **PRD**: docs/prds/[name].md
- **Branch**: feat/[name]
- **Files Created**: [list]
- **Files Modified**: [list]
- **Tests**: X tests, all passing
- **Coverage**: Y%
- **Open Items**: [if any]
```
