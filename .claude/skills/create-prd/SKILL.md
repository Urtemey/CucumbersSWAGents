---
name: create-prd
description: "Create a Product Requirements Document following project template"
argument-hint: "<feature description>"
---

# /create-prd — Create PRD

## Trigger
`/create-prd "feature description"`

## Workflow

### Step 1: Understand the Feature
- Ask clarifying questions if the description is vague
- Research the existing codebase for relevant context
- Identify the problem being solved

### Step 2: Define the Problem
- Describe current state and shortcomings
- Provide evidence (data, user feedback, metrics)
- Quantify the impact

### Step 3: Identify Users
- Define target audience segments
- Document their needs and pain points
- Prioritize segments

### Step 4: Write User Scenarios
- Create scenarios with GIVEN/WHEN/THEN
- Assign unique IDs (AC-001, AC-002...)
- Include input/output example tables
- Cover happy paths AND error cases

### Step 5: Define Scope
- Explicitly list what IS included
- Explicitly list what is NOT included
- Note possible future extensions

### Step 6: Technical Context
- Identify components (frontend, backend, DB)
- Draft API specifications
- Note constraints (performance, scale, compatibility)

### Step 7: Quality Requirements
- Performance targets (response time, throughput)
- Reliability targets (uptime, error rates)
- Test coverage thresholds

### Step 8: Development Plan
- Break into phases: Data Layer → Business Logic → API/Interface
- Each phase has clear deliverables

## Output
Save PRD to `docs/prds/[feature-name].md` using template from `docs/templates/PRD-TEMPLATE.md`.

## Writing Guidelines
- Be specific: "reduce p95 latency below 200ms" not "improve performance"
- Use concrete examples with sample input/output
- Make every criterion testable
- Include both "Included" and "Excluded" scope sections
- Think in edge cases: empty input, null, huge, malicious

## Validation Checklist
- [ ] Every scenario has GIVEN/WHEN/THEN
- [ ] Every criterion has unique ID
- [ ] Every criterion is independently testable
- [ ] Scope has both Included and Excluded sections
- [ ] At least one error/edge case scenario
- [ ] Development phases ordered by dependency
