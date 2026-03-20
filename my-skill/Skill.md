# PRD Creator Skill

## Description
Creates Product Requirements Documents following the project's PRD standard template. Ensures all PRDs are consistent, complete, and actionable.

## When to Use
- When a new feature needs a formal PRD
- When `/new-feature` is invoked (Phase 1)
- When the user asks to document requirements for a feature

## Workflow

### Step 1: Understand the Feature
- Ask clarifying questions if the description is vague
- Research the existing codebase for relevant context
- Identify the problem being solved

### Step 2: Define the Problem
- Describe the current state and its shortcomings
- Provide evidence (data, user feedback, metrics)
- Quantify the impact

### Step 3: Identify Users
- Define target audience segments
- Document their needs and pain points
- Prioritize segments

### Step 4: Write User Scenarios
- Create concrete scenarios with GIVEN/WHEN/THEN
- Assign unique IDs (AC-001, AC-002...)
- Include input/output example tables
- Cover happy paths AND error cases

### Step 5: Define Scope
- Explicitly list what IS included
- Explicitly list what is NOT included (equally important)
- Note possible future extensions

### Step 6: Technical Context
- Identify components needed (frontend, backend, DB)
- Draft API specifications
- Note constraints (performance, scale, compatibility)

### Step 7: Quality Requirements
- Define performance targets (response time, throughput)
- Define reliability targets (uptime, error rates)
- Set test coverage thresholds

### Step 8: Development Plan
- Break into phases: Data Layer → Business Logic → API/Interface
- Each phase has clear deliverables
- Phases are independently deployable when possible

## Output
Save the completed PRD to `docs/prds/[feature-name].md` following the template in `Create-PRD.md`.

## Writing Guidelines
- **Be specific** — "reduce p95 latency below 200ms" not "improve performance"
- **Use concrete examples** — Every scenario has sample input/output
- **Make it testable** — If you can't write a test for a criterion, rewrite it
- **Avoid jargon** — Write for a technical audience, but be clear
- **Think in edges** — What happens when input is empty? Null? Huge? Malicious?

## Validation Checklist
- [ ] Every scenario has GIVEN/WHEN/THEN
- [ ] Every acceptance criterion has a unique ID
- [ ] Every criterion is independently testable
- [ ] Scope includes both "Included" and "Excluded" sections
- [ ] At least one error/edge case scenario
- [ ] Input/output examples for each scenario
- [ ] Development phases are ordered by dependency
