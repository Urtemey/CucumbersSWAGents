# Create-PRD — Product Requirements Document Template

Use this template when creating PRDs for new features. PRDs are saved to `docs/prds/[feature-name].md`.

---

## PRD Template

```markdown
# PRD: [Feature Name]

| Field | Value |
|-------|-------|
| **Stage** | draft / review / approved / implementing / done |
| **Owner** | [name] |
| **Priority** | P0 / P1 / P2 / P3 |
| **Stakeholders** | [list] |
| **Created** | YYYY-MM-DD |
| **Updated** | YYYY-MM-DD |

---

## 1. Overview

### Strategic Goal
Brief description of the feature and its strategic purpose.

### Success Metrics
- Metric 1: target value
- Metric 2: target value

## 2. Problem Description

### Current State
What exists today and what's wrong with it.

### Evidence
- Data points, user feedback, metrics.

### Impact
Who is affected and how severely.

## 3. Target Audience

| Segment | Description | Key Needs |
|---------|-------------|-----------|
| Segment 1 | Who they are | What they need |

## 4. User Scenarios

### Scenario 1: [Name]

**Acceptance Criteria ID**: AC-001

**GIVEN** [precondition]
**WHEN** [action]
**THEN** [expected result]

| Input | Expected Output |
|-------|----------------|
| example input | example output |

### Scenario 2: [Name]

**Acceptance Criteria ID**: AC-002

**GIVEN** [precondition]
**WHEN** [action]
**THEN** [expected result]

## 5. Functional Scope

### Included
- What IS part of this feature

### Excluded
- What is NOT part of this feature

### Future Extensions
- What MIGHT be added later

## 6. Technical Environment

### Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | TBD | User interface |
| Backend | TBD | Business logic, API |
| Database | TBD | Data persistence |

### API Specification

```
METHOD /api/endpoint
Request: { field: type }
Response: { field: type }
Status codes: 200, 400, 401, 404, 500
```

### Constraints
- Performance targets
- Scalability requirements
- Compatibility requirements

## 7. UX / Interaction Design

### User Flow
```
[Start] → [Step 1] → [Decision] → [Step 2] → [Result]
```

### Error Handling

| Error Condition | User Message | Recovery Action |
|----------------|-------------|-----------------|
| Invalid input | "Please check..." | Highlight field |
| Server error | "Something went wrong..." | Retry button |

## 8. Quality Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| Performance | API response time | < 200ms (p95) |
| Reliability | Uptime | 99.9% |
| Accessibility | WCAG level | AA |
| Test Coverage | Line coverage | ≥ 80% |

## 9. Development Plan

### Phase 1: Data Layer
- Database schema / models
- Data access layer
- Migrations

### Phase 2: Business Logic
- Core domain logic
- Validation rules
- Service layer

### Phase 3: API / Interface
- Endpoints / UI components
- Input validation
- Error responses

## 10. Deployment Strategy

- [ ] Feature flag: `FEATURE_NAME_ENABLED`
- [ ] Rollout plan: canary → 10% → 50% → 100%
- [ ] Rollback procedure documented
- [ ] Monitoring/alerting configured

## 11. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Risk 1 | High/Med/Low | High/Med/Low | Mitigation plan |

## 12. Agent Operating Rules

**Allowed:**
- Read all project files
- Create/modify files within feature scope
- Create branches, run tests and builds

**Requires Approval:**
- Adding new dependencies
- Changing database schemas or API contracts
- Modifying CI/CD pipelines

**Forbidden:**
- Committing secrets or credentials
- Removing security measures
- Skipping tests
- Deploying to production

## 13. Completion Checklist

- [ ] All acceptance criteria (AC-*) have corresponding tests
- [ ] All tests pass
- [ ] Code review completed — no Critical findings
- [ ] Documentation updated
- [ ] Performance targets met
- [ ] Security review passed
```

---

## PRD Writing Guidelines

1. **Be specific** — Avoid vague language ("improve performance" → "reduce p95 latency below 200ms").
2. **Use examples** — Every scenario should have concrete input/output examples.
3. **Make it testable** — If you can't write a test for it, rewrite the criterion.
4. **Limit scope** — The "Excluded" section is as important as "Included".
5. **Think in phases** — Break implementation into deliverable chunks.

## Acceptance Criteria Rules

- Use GIVEN/WHEN/THEN format consistently.
- Each criterion has a unique ID (AC-001, AC-002...).
- Each criterion must be independently testable.
- Include both happy path and error cases.
- Specify exact expected outputs, not just "should work correctly".
